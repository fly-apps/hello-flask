import requests
import base64
import os
import json
import datetime
import logging
import http
from pprint import pformat
from pytz import timezone
from flask import Flask, request, redirect, Response
from dotenv import load_dotenv
from openai import OpenAI

#http.client.HTTPConnection.debuglevel = 1

load_dotenv()

app = Flask(__name__)

mock_task = json.loads('{"title": "Plan Hot Air Balloon Trip", "dueDate": "2023-12-16T00:00:00-08:00", "content": "- [ ] Research local hot air balloon companies\\n- [ ] Compare pricing and reviews\\n - [ ] Check the weather forecast for this weekend\\n - [ ] Contact chosen company to book a flight\\n - [ ] Confirm booking and payment details\\n - [ ] Prepare camera equipment for aerial photos\\n - [ ] Notify participants of the trip details", "startDate": "2023-12-15T00:00:00-08:00", "timeZone": "America/Los_Angeles", "isAllDay": true}')

def convert_image_to_task(encoded_image: str) -> dict:
    """
    Converts an encoded image into a task by sending to OpeNAI to analyzing 
    the image, generating a summary of the image and generating a TickTick 
    task in JSON format.

    Args:
        encoded_image (str): The base64-encoded image.

    Returns:
        dict: A TickTick task in JSON format.

    Raises:
        None
    """
    client = OpenAI()

    prompt_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """
Take on the persona of my personal assistant.

Please analyze this image and respond with a task in the format of a task for me to do.

Format your response as TickTick task in JSON format that can be sent to ticktick via their api.
Only send the json in your response, do not return any non-json text, numbering, or formatting:

 - Use a summary for the task name. 
 - Include possible sub-actions as properly formatted checkboxes in the item content. 
 - Set the task due date to today. 
 - Include any relevant deadlines for in the task content or task name. 
 - Include relevant URLs or text content as well.

Use markdown formatting only in the task content, no HTML.
Do not include the string "\n```json" in your response.
"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}"
                    }
                }
            ]
        }
    ]

    # Send a request to GPT
    params = {
        "model": "gpt-4-vision-preview",
        "messages": prompt_messages,
        "max_tokens": 4096
    }

    completion = client.chat.completions.create(**params)
    app.logger.debug(completion.choices[0].message.content)

    task = json.loads(completion.choices[0].message.content)
    return task

def create_ticktick_task(task: dict):
    """
    Create a TickTick task using the provided task dictionary.

    Args:
        task (dict): A dictionary containing the details of the task.

    Returns:
        dict: A dictionary containing the response from the TickTick API.
    """

    ## get a datetime object that is today (Pacific) and at midnight
    now = datetime.datetime.now(timezone('America/Los_Angeles'))
    now.replace(hour=0, minute=0, second=0, microsecond=0)

    ## set the attributes on the task that we don't want OpenAI to handle
    task['startDate'] = now.strftime("%Y-%m-%dT%H:%M:%S+0000")
    task['dueDate'] = now.strftime("%Y-%m-%dT%H:%M:%S+0000")
    task['isAllDay'] = True
    if 'priority' in task: del task['priority'] 

    ## send the task to TickTick
    headers = {
        "Authorization": "Bearer " + os.environ.get('TICKTICK_ACCESS_TOKEN')
    }

    app.logger.debug(f">>>>>> Task to TickTick:\r\n {pformat(task)}")

    response = requests.post("https://api.ticktick.com/open/v1/task", json=task, headers=headers)

    app.logger.debug(f">>>>>> Task from TickTick:\r\n {pformat(response.json())}")

    return response.json()

@app.route('/task-from-image', methods=['POST'])
def task_from_image():
    
    if 'image' not in request.form:
        return "No image sent", 400

    task = mock_task

    if 'mock' not in request.form:
        task = convert_image_to_task(request.form['image'])

    return create_ticktick_task(task)

if __name__ == '__main__':
    app.run()