"""Stop only the current Runpod pod by an absolute UTC deadline.

Uses the pod-scoped Runpod credential injected into the container, held only in
memory. This is independent of the experiment process. A provider stop erases
temporary container storage; /workspace persists only on a retained volume.
"""
import argparse
import datetime as dt
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def injected_environment():
    return dict(item.decode().split("=", 1) for item in Path("/proc/1/environ").read_bytes().split(b"\0") if b"=" in item)


def request(environment, method):
    pod = environment["RUNPOD_POD_ID"]
    operation = "podStop" if method == "POST" else "pod"
    kind = "mutation" if method == "POST" else "query"
    query = kind + " { " + operation + "(input: {podId: " + json.dumps(pod) + "}) { id desiredStatus } }"
    # The injected pod-scoped credential works with GraphQL; REST v1 returned 403.
    req = urllib.request.Request("https://api.runpod.io/graphql", method="POST", headers={
        "Authorization": "Bearer " + environment["RUNPOD_API_KEY"],
        "Content-Type": "application/json",
        "User-Agent": "sae-anchor-smoke/1.0",
    }, data=json.dumps({"query": query}).encode())
    with urllib.request.urlopen(req, timeout=30) as response:
        body = json.load(response)
        state = body.get("data", {}).get(operation)
        if body.get("errors") or not state or state.get("id") != pod:
            raise RuntimeError("Runpod did not confirm the requested pod operation")
        return response.status, state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pod-id", required=True)
    parser.add_argument("--deadline", help="ISO UTC timestamp")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stop-now", action="store_true")
    args = parser.parse_args()
    environment = injected_environment()
    if environment.get("RUNPOD_POD_ID") != args.pod_id:
        raise RuntimeError("Pod identity mismatch")
    status, state = request(environment, "GET")
    print(json.dumps({"api_status": status, "pod_id": args.pod_id,
                      "desired_status": state.get("desiredStatus")}), flush=True)
    if args.check:
        return
    if not args.stop_now:
        deadline = dt.datetime.fromisoformat(args.deadline.replace("Z", "+00:00")).timestamp()
        print(json.dumps({"stop_deadline_utc": args.deadline}), flush=True)
        while time.time() < deadline:
            time.sleep(min(30, max(0, deadline - time.time())))
    for attempt in range(5):
        try:
            status, _ = request(environment, "POST")
            print(json.dumps({"stop_requested": True, "http_status": status}), flush=True)
            return
        except (urllib.error.URLError, RuntimeError, TimeoutError) as error:
            print(json.dumps({"stop_requested": False, "http_status": getattr(error, "code", None),
                              "attempt": attempt + 1}), flush=True)
            time.sleep(10)
    raise RuntimeError("Runpod API stop failed; manual stop required")


if __name__ == "__main__":
    main()
