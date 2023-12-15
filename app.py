import requests
import base64
import os
import json
from pytz import timezone
from datetime import datetime
from flask import Flask, request, redirect, Response
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

app = Flask(__name__)

@app.route('/task-from-image', methods=['POST'])
def task_from_image():
    encoded_image = request.form['image']

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
    # print(completion.choices[0].message.content)

    task = json.loads(completion.choices[0].message.content)
    
    now = datetime.now(timezone('America/Los_Angeles')).replace(hour=0, minute=0, second=0, microsecond=0)

    task['startDate'] = now.isoformat()
    # task['dueDate'] = now.isoformat()
    task['timezone'] = 'America/Los_Angeles'
    # task['isAllDay'] = True

    headers = {
        "Authorization": "Bearer " + os.environ.get('TICKTICK_ACCESS_TOKEN')
    }

    response = requests.post("https://ticktick.com/open/v1/task", json=task, headers=headers)

    print(response.json())

    return Response(response=completion.choices[0].message.content,
                    status=200,
                    mimetype="application/json")

if __name__ == '__main__':
    app.run()