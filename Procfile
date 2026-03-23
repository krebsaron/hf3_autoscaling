web: locust -f locustfile.py --host ${TARGET_HOST} --web-host 0.0.0.0 --web-port ${PORT}
worker: locust -f locustfile.py --headless --host ${TARGET_HOST} --users ${LOCUST_USERS:-15} --spawn-rate ${LOCUST_SPAWN_RATE:-1} --run-time ${LOCUST_RUN_TIME:-8m}
