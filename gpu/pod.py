"""Control a RunPod GPU pod from this project.

  python3 gpu/pod.py start            # rent a GPU pod (prints its id)
  python3 gpu/pod.py status           # show running pods + spend per hour
  python3 gpu/pod.py exec "nvidia-smi" [--wait]
  python3 gpu/pod.py job <id>         # show a job's log tail
  python3 gpu/pod.py put local remote # upload a file
  python3 gpu/pod.py get remote local # download a file
  python3 gpu/pod.py stop             # terminate the pod (stops all charges)

The RunPod API key is injected by the network proxy; pod id + secret are kept in gpu/.pod.json.
"""
import base64, json, os, secrets, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".pod.json")
GPU = os.environ.get("POD_GPU", "NVIDIA RTX A6000")
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"


def gql(query):
    req = urllib.request.Request("https://api.runpod.io/graphql", json.dumps({"query": query}).encode(),
                                 {"content-type": "application/json", "Authorization": "Bearer proxy-injected"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    if "errors" in d:
        raise SystemExit(json.dumps(d["errors"], indent=1))
    return d["data"]


def state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def call(method, path, body=None, raw=False, timeout=120):
    s = state()
    url = f"https://{s['id']}-8000.proxy.runpod.net{path}"
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(url, data, {"X-Secret": s["secret"], "User-Agent": "paper-cinema/1.0"}, method=method)
    r = urllib.request.urlopen(req, timeout=timeout).read()
    return r if raw else json.loads(r)


def main():
    cmd = sys.argv[1]
    if cmd == "start":
        secret = secrets.token_hex(16)
        agent = base64.b64encode(open(os.path.join(HERE, "agent.py"), "rb").read()).decode()
        docker_args = f"bash -c 'echo {agent} | base64 -d > /agent.py && python3 /agent.py'"
        q = f'''mutation {{ podFindAndDeployOnDemand(input: {{
            cloudType: {os.environ.get("POD_CLOUD", "COMMUNITY")}, gpuCount: 1, gpuTypeId: "{GPU}",
            name: "paper-cinema-3d", imageName: "{IMAGE}", dockerArgs: {json.dumps(docker_args)},
            ports: "8000/http", containerDiskInGb: {os.environ.get("POD_DISK", "40")}, volumeInGb: 0,
            env: [{{ key: "SECRET", value: "{secret}" }}] }}) {{ id costPerHr machine {{ gpuDisplayName }} }} }}'''
        p = gql(q)["podFindAndDeployOnDemand"]
        json.dump({"id": p["id"], "secret": secret}, open(STATE, "w"))
        print("started pod", p["id"], p["machine"], "$/hr", p["costPerHr"])
    elif cmd == "status":
        print(json.dumps(gql("{ myself { currentSpendPerHr clientBalance pods { id name desiredStatus costPerHr runtime { uptimeInSeconds } } } }")["myself"], indent=1))
    elif cmd == "stop":
        s = state()
        print(gql(f'mutation {{ podTerminate(input: {{ podId: "{s["id"]}" }}) }}'))
        os.remove(STATE)
        print("pod terminated — no more charges")
    elif cmd == "health":
        s = state()
        print(urllib.request.urlopen(urllib.request.Request(f"https://{s['id']}-8000.proxy.runpod.net/health", headers={'User-Agent': 'paper-cinema/1.0'}), timeout=30).read().decode())
    elif cmd == "exec":
        j = call("POST", "/exec", {"cmd": sys.argv[2]})
        print("job", j["id"])
        if "--wait" in sys.argv:
            while True:
                r = call("GET", f"/job?id={j['id']}")
                if not r["running"]:
                    print(r["tail"]); print("exit code", r["code"]); break
                time.sleep(10)
    elif cmd == "job":
        r = call("GET", f"/job?id={sys.argv[2]}&tail={sys.argv[3] if len(sys.argv) > 3 else 3000}")
        print(r["tail"]); print("running" if r["running"] else f"exit code {r['code']}")
    elif cmd == "put":
        print(call("POST", f"/file?path={sys.argv[3]}", open(sys.argv[2], "rb").read(), timeout=600))
    elif cmd == "get":
        open(sys.argv[3], "wb").write(call("GET", f"/file?path={sys.argv[2]}", raw=True, timeout=600))
        print("saved", sys.argv[3])


if __name__ == "__main__":
    main()
