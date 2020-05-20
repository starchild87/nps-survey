import os
import requests
from airtable import Airtable
from flask import Flask, request, session
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')

# This is required to read/write from AirTable base (GET/POST)
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

message_data_dict = {}

@app.route('/send-survey', methods=['POST'])
def send_survey():
    """
    a function that sends the SMS autoresponder
    messages and writes to the AirTable
    """
    airtable = Airtable(AIRTABLE_BASE_ID, 'Input')
    incoming_msg = request.values.get('Body', '').lower()
    sender_phone_number = request.values.get('From', '')
    twilio_phone_number = request.values.get('To', '')
    global message_data_dict

    # reset session
    if 'reset' in incoming_msg:
        del session['sms_count']
        return("resetting the session")
        
    if not 'sms_count' in session:
        session['sms_count'] = 0
        
    sms_count = session['sms_count']
    sms_message = get_message(sms_count)
    
    if sms_count >= 0 and sms_count <= 3:
        if sms_count == 0:
            message_data_dict[sender_phone_number] = {}
            message_data_dict[sender_phone_number]['Twilio_Phone_Number'] = twilio_phone_number
        elif sms_count == 1:
            message_data_dict[sender_phone_number]['Score'] = int(incoming_msg)
        elif sms_count == 2:
            message_data_dict[sender_phone_number]['Reason'] = incoming_msg
        elif sms_count == 3:
            message_data_dict[sender_phone_number]['Comments'] = incoming_msg
            # here is where we write to the airtable
            airtable.insert(message_data_dict[sender_phone_number])
        session['sms_count'] += 1
    
    print(message_data_dict)

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(sms_message)

    return str(resp)

@app.route('/get-scores', methods=['GET'])
def get_scores():
    """
    function that gets the scores from the airtable base
    """
    phone_number = str(request.args.get('number'))

    airtable = Airtable(AIRTABLE_BASE_ID, 'Input')
    airtable_data_dict = {}
    score_list = []

    for page in airtable.get_iter(view='nps', filterByFormula="({Twilio_Phone_Number}=" + phone_number + ")"):
        for record in page:
            num_id = record['fields']['ID']
            airtable_data_dict[num_id] = {}
            airtable_data_dict[num_id]['score'] = record['fields']['Score']
            airtable_data_dict[num_id]['reason'] = record['fields']['Reason']
            airtable_data_dict[num_id]['comments'] = record['fields']['Comments']

            score_list.append(record['fields']['Score'])
    nps_total_score = calc_nps(score_list)

    return {'overallNPS': nps_total_score, 'airtableData': airtable_data_dict}

def calc_nps(scores):
    """
    a function that calculates the total NPS score from an event
    """
    promoters = 0
    neutral = 0
    detractors = 0
    for score in scores:
        if score >= 9:
            promoters += 1
        elif score >= 7:
            neutral += 1
        else:
            detractors += 1

    nps_total = (promoters - detractors) / len(scores) * 100

    return nps_total

def get_message(sms_count):
    """
    a function that gets the text message body as a string
    """
    if sms_count == 0:
        sms_message = "On a scale of 1 (not likely) to 10 (extremely likely) how likely are you to recommend Twilio to a friend or colleague?”"
    elif sms_count == 1:
        sms_message = "Why did you give us that score?"
    elif sms_count == 2:
        sms_message = "Is there anything we could do better next time?"
    else:
        sms_message = "Thanks for your responses!"
    return sms_message
