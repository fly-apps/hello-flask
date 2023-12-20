import requests
import base64
import os
import io
import json
import datetime
import logging
import http
from pprint import pformat,pprint
from pytz import timezone
from flask import Flask, request, redirect, Response, send_file, render_template, make_response
from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_path, convert_from_bytes


#http.client.HTTPConnection.debuglevel = 1

load_dotenv()

app = Flask(__name__)

mock_task = json.loads('{"title": "Plan Hot Air Balloon Trip", "dueDate": "2023-12-16T00:00:00-08:00", "content": "- [ ] Research local hot air balloon companies\\n- [ ] Compare pricing and reviews\\n - [ ] Check the weather forecast for this weekend\\n - [ ] Contact chosen company to book a flight\\n - [ ] Confirm booking and payment details\\n - [ ] Prepare camera equipment for aerial photos\\n - [ ] Notify participants of the trip details", "startDate": "2023-12-15T00:00:00-08:00", "timeZone": "America/Los_Angeles", "isAllDay": true}')

def convert_image_to_task(encoded_images: [str], query_suffix="") -> dict:
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

    query = f"""
Take on the persona of my personal assistant.

Please analyze the following email. Consider any uploaded images or documents as attachments 
to the email. Act as my personal assistant would, thinking critically about the purpose and 
content of the email and the attachments, and respond with a task for me to do.

Format your response as TickTick task in JSON format that can be sent to ticktick via their api.
Only send the json in your response, do not return any non-json text, numbering, or formatting:

 - Use a summary for the task name. 
 - Include possible sub-actions as properly formatted checkboxes in the item content. 
 - Set the task due date to today. 
 - Include any relevant deadlines for in the task content or task name. 
 - Include relevant URLs or text content as well.

Use markdown formatting only in the task content, no HTML.
Do not include the string "\n```json" in your response.

{query_suffix}
"""

    prompt_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": query
                }
            ]
        }
    ]

    for encoded_image in encoded_images:
        prompt_messages[0]['content'].append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encoded_image}"
            }
        })

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
        task = convert_image_to_task([request.form['image']])

    return create_ticktick_task(task)


def get_image_in_jpeg64(image):
    fn = "./static/tmptest.jpg"
    r = ""
    image.save(fn)
    with open(fn, 'rb') as fp:
        r = base64.b64encode(fp.read()).decode('utf-8')
        os.remove(fn)

    return r

def get_query_suffix(html):
    return f"""
Here is the email content:
-------
{html}
"""

# cloudmailin version
# @app.route('/', methods=['POST'])
# @app.route('/task-from-email-cloudmailin', methods=['POST'])
# def task_from_email_cloudmailin():
#     pprint(request.form['attachment1'])
#     file_bytes = base64.b64decode(request.json['attachments'][0]['content'])
#     images: List[Image.Image] = convert_from_bytes(file_bytes,fmt="JPEG")
#     encoded_images = [get_image_in_jpeg64(im) for im in images]

#     if 'mock' not in request.json:
#         task = convert_image_to_task(encoded_images, query_suffix=get_query_suffix(request.json['html']))

#     pprint(task)

#     return create_ticktick_task(task)


# sendgrid version
# @app.route('/', methods=['POST'])
# @app.route('/task-from-email', methods=['POST'])
# def task_from_email_form():
#     encoded_images = []

#     pprint(request.files)
    
#     for attachment in request.files.values():
#         attachment.save('static/test.pdf')
#         attachment.seek(0)
#         file_bytes = attachment.read()
#         images: List[Image.Image] = convert_from_bytes(file_bytes,fmt="JPEG")
#         encoded_images.append([get_image_in_jpeg64(im) for im in images])

#     return "OK"

#     print(len(encoded_images))

#     if 'mock' not in request.form:
#         task = convert_image_to_task(encoded_images, query_suffix=get_query_suffix(request.form['html']))

#     return create_ticktick_task(task)

@app.route('/', methods=['POST'])
@app.route('/task-from-email-json', methods=['POST'])
def task_from_email():

    encoded_images = []

    def convert_pdf_to_jpeg64(content):
        file_bytes = base64.b64decode(content)
        images: List[Image.Image] = convert_from_bytes(file_bytes,fmt="JPEG")
        encoded_images = [get_image_in_jpeg64(im) for im in images]
        return encoded_images

    def convert_jpeg_to_jpeg64(content):
        return base64.b64decode(content)

    processors = {
        'application/pdf': convert_pdf_to_jpeg64,
        'application/jpeg': convert_jpeg_to_jpeg64
    }

    for attachment in request.json['Attachments']:
        encoded_images.append(processors[attachment['Content-Type:']](attachment['Content']))

    if 'mock' not in request.json:
        task = convert_image_to_task(encoded_images, query_suffix=get_query_suffix(request.json['TextBody']))

    pprint(task)

    return create_ticktick_task(task)
    


if __name__ == '__main__':
    app.run()