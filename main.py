import json
import requests
import asyncio
import time

with open("api.json", "r") as file:
    config = json.load(file)

phone_number = ""
success_count = 0
failure_count = 0
total_requests_sent = 0
api_cooldown = {}

async def make_request(api, phone_number):
    global success_count, failure_count, total_requests_sent

    api["url"] = api["url"].format(phone_number=phone_number)
    if "params" in api:
        for key in api["params"]:
            if isinstance(api["params"][key], str):
                api["params"][key] = api["params"][key].format(phone_number=phone_number)

    headers = api["headers"]

    if api["name"] in api_cooldown:
        cooldown_time = api_cooldown[api["name"]]
        if time.time() < cooldown_time:
            print(f"API {api['name']} is in cooldown. Skipping request.")
            return 

    try:
        if api["method"] == "POST":
            if headers.get("Content-Type") == "application/json":
                response = await asyncio.to_thread(requests.post, api["url"], headers=headers, json=api["params"])
            else:
                response = await asyncio.to_thread(requests.post, api["url"], headers=headers, data=api["params"])
        elif api["method"] == "GET":
            response = await asyncio.to_thread(requests.get, api["url"], headers=headers, params=api["params"])

        total_requests_sent += 1
        print(f"Response from {api['name']}: Status Code {response.status_code}")


        if response.status_code == 400 or response.status_code == 429:
            cooldown_time = time.time() + 5  
            api_cooldown[api["name"]] = cooldown_time
            print(f"API {api['name']} hit rate limit or bad request. Cooling down for 1 minute.")
            failure_count += 1
        elif api["identifier"] in response.text:
            success_count += 1
            print(f"API {api['name']} request was successful.")
        else:
            failure_count += 1
            print(f"API {api['name']} failed: Identifier not found.")
        
    except requests.RequestException as e:
        failure_count += 1
        print(f"Request failed for {api['name']} with error: {e}")

async def main():
    global success_count, failure_count, total_requests_sent

    while True:
        tasks = []
        for api in config["api"]:
            task = make_request(api, phone_number)
            tasks.append(task)

        await asyncio.gather(*tasks)
        await asyncio.sleep(1)

        print("\n--- Request Summary ---")
        print(f"Total Requests Sent: {total_requests_sent}")
        print(f"Successful Requests: {success_count}")
        print(f"Failed Requests: {failure_count}")
        print("----------------------\n")

if __name__ == "__main__":
    asyncio.run(main())
