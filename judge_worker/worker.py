import json
import time
import docker
import pika
import redis
import os
import concurrent.futures

# Initialize Docker client
try:
    client = docker.from_env()
    print("Successfully connected to Docker daemon.")
except Exception as e:
    print(f"Failed to connect to Docker daemon: {e}")
    exit(1)

# Initialize Redis client for SSE broadcasting
try:
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    redis_password = os.environ.get('REDIS_PASSWORD', None)
    redis_ssl = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
    
    redis_client = redis.Redis(host=redis_host, port=redis_port, password=redis_password, db=0, decode_responses=True, ssl=redis_ssl)
    redis_client.ping()
    print(f"Successfully connected to Redis at {redis_host}.")
except Exception as e:
    print(f"Failed to connect to Redis: {e}")

def run_judge(submission_id: int, code: str, language: str, input_data: str = "", expected_output: str = "", timeout: int = 2):
    print(f"Judging submission {submission_id} in {language}...")
    
    if language.lower() != "python":
        return {"status": "error", "message": "Only python is supported in Phase 3."}

    start_time = time.time()
    internal_exec_time = None
    memory_kb = 0
    
    wrapper_script = (
        "import os, sys, subprocess, time, resource\n"
        "with open('main.py', 'w', encoding='utf-8') as f:\n"
        "    f.write(os.environ.get('CODE', ''))\n"
        "with open('input.txt', 'w', encoding='utf-8') as f:\n"
        "    f.write(os.environ.get('INPUT_DATA', ''))\n"
        "start = time.time()\n"
        "res = subprocess.run(['python', 'main.py'], stdin=open('input.txt', 'r'), capture_output=True, text=True)\n"
        "exec_time = time.time() - start\n"
        "ru = resource.getrusage(resource.RUSAGE_CHILDREN)\n"
        "sys.stdout.write(res.stdout)\n"
        "sys.stderr.write(res.stderr)\n"
        "sys.stderr.write(f'\\n[EXEC_STATS]: {exec_time:.3f} {ru.ru_maxrss}\\n')\n"
        "sys.exit(res.returncode)\n"
    )
    
    try:
        container = client.containers.run(
            image="python:3.10-slim",
            command=["python", "-c", wrapper_script],
            environment={"CODE": code, "INPUT_DATA": input_data},
            network_mode="none",
            mem_limit="256m",
            pids_limit=64,
            cap_drop=["ALL"],
            user="nobody",
            working_dir="/tmp",
            detach=True
        )
        
        try:
            result = container.wait(timeout=timeout)
            exit_code = result['StatusCode']
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr_full = container.logs(stdout=False, stderr=True).decode('utf-8')
            
            stderr_lines = []
            for line in stderr_full.splitlines():
                if line.startswith("[EXEC_STATS]:"):
                    parts = line.split(":")[-1].strip().split()
                    try:
                        internal_exec_time = float(parts[0])
                        memory_kb = int(parts[1])
                    except:
                        pass
                elif line.strip() != "":
                    stderr_lines.append(line)
            stderr = "\n".join(stderr_lines)
            
            if exit_code != 0:
                status = "ERROR"
                output = stderr
            else:
                output = stdout
                # Check if it matches expected answer
                if expected_output and output.strip() == expected_output.strip():
                    status = "SUCCESS"
                else:
                    status = "FAIL"
        except Exception as wait_err:
            container.kill()
            status = "timeout"
            output = "Execution timed out."
            exit_code = 124
        finally:
            container.remove(force=True)
            
    except Exception as e:
        status = "system_error"
        output = str(e)
        exit_code = -1

    exec_time = time.time() - start_time
    final_exec_time = internal_exec_time if internal_exec_time is not None else round(exec_time, 3)
    return {
        "submission_id": submission_id,
        "status": status,
        "output": output,
        "exec_time": final_exec_time,
        "memory_kb": memory_kb,
        "exit_code": exit_code
    }

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        submission_id = data.get("submission_id")
        code = data.get("code")
        language = data.get("language", "python")
        timeout = data.get("timeout", 2)
        test_cases = data.get("testCases")
        
        if not test_cases or not isinstance(test_cases, list):
            test_cases = [{
                "input": data.get("input_data", ""),
                "expected_output": data.get("expected_output", "")
            }]

        print(f"Starting parallel judge for submission {submission_id} with {len(test_cases)} test cases.")

        results = []
        overall_status = "SUCCESS"
        total_start_time = time.time()

        def judge_single_tc(idx_tc_pair):
            idx, tc = idx_tc_pair
            inp = tc.get("input", "")
            exp = tc.get("expected_output", tc.get("expectedOutput", ""))
            res = run_judge(submission_id, code, language, inp, exp, timeout)
            res["index"] = idx
            
            tc_result_event = {
                "submission_id": submission_id,
                "type": "TESTCASE_RESULT",
                "index": idx,
                "total": len(test_cases),
                "status": res["status"],
                "output": res["output"],
                "exec_time": res["exec_time"],
                "memory_kb": res.get("memory_kb", 0),
                "input": inp,
                "expected_output": exp
            }
            redis_client.publish('judge_events', json.dumps(tc_result_event))
            print(f"Published TESTCASE_RESULT #{idx} for submission {submission_id}: status={res['status']}")
            return res

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(test_cases), 5)) as executor:
            future_to_idx = {executor.submit(judge_single_tc, (idx, tc)): idx for idx, tc in enumerate(test_cases, 1)}
            for future in concurrent.futures.as_completed(future_to_idx):
                res = future.result()
                results.append(res)
                if res["status"] != "SUCCESS":
                    if res["status"] in ["ERROR", "system_error"]:
                        overall_status = "ERROR"
                    elif res["status"] == "timeout" and overall_status != "ERROR":
                        overall_status = "TIMEOUT"
                    elif overall_status not in ["ERROR", "TIMEOUT"]:
                        overall_status = "FAIL"

        total_exec_time = round(time.time() - total_start_time, 3)

        summary_lines = [f"--- All {len(test_cases)} Test Cases Completed in {total_exec_time}s ---"]
        for idx, res in enumerate(sorted(results, key=lambda r: r.get("index", 0)), 1):
            summary_lines.append(f"[TC #{idx}] Status: {res['status']} ({res['exec_time']}s / {res.get('memory_kb', 0)}KB)")
            if res['status'] != "SUCCESS":
                summary_lines.append(f"   Output: {res['output'].strip()}")

        final_result = {
            "submission_id": submission_id,
            "type": "SUBMISSION_COMPLETE",
            "status": overall_status,
            "output": "\n".join(summary_lines),
            "total_exec_time": total_exec_time
        }
        redis_client.publish('judge_events', json.dumps(final_result))
        print(f"Published SUBMISSION_COMPLETE for submission {submission_id}: overall={overall_status}")
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    # Connect to RabbitMQ
    # Retry mechanism could be added here for production readiness
    rabbitmq_host = os.environ.get('RABBITMQ_HOST', 'localhost')
    rabbitmq_port = int(os.environ.get('RABBITMQ_PORT', 5672))
    rabbitmq_user = os.environ.get('RABBITMQ_USERNAME', 'guest')
    rabbitmq_pass = os.environ.get('RABBITMQ_PASSWORD', 'guest')
    rabbitmq_vhost = os.environ.get('RABBITMQ_VHOST', '/')
    
    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, credentials=credentials, virtual_host=rabbitmq_vhost)
    )
    channel = connection.channel()
    
    # Declare queue
    channel.queue_declare(queue='judge_queue', durable=True)
    channel.basic_qos(prefetch_count=1)
    
    # Start consuming
    channel.basic_consume(queue='judge_queue', on_message_callback=callback)
    
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    main()
