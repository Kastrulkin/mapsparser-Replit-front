
def debug_log(msg):
    try:
        with open("worker_debug.txt", "a") as f:
            f.write(f"{datetime.now()}: {msg}\n")
    except:
        pass
