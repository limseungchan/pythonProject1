import json
from flask import Flask, request, make_response, jsonify, abort, render_template
import sys
from firebase_admin import credentials, firestore, initialize_app
import ssl
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, Action, URIAction, DatetimePickerAction,
    ButtonsTemplate, TemplateSendMessage
)

myapp = Flask(__name__)
log = myapp.logger

line_bot_api = LineBotApi(
    'Vsf16xlCfAZSJSHXgrH+ReXdQ/54rwswvMnSLWCMP6pnuLFgUQyG5MkQwxitpfktEdEMPBrkNukXNCN6Y+pO8D3J4/feGZEz4k4RMX7XOP5jtZdCZS3uRR5ZLXaMdQ2yCkhdj+A+6UsnehrwvPSWUwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('6563d87f4e2b10df141ba0225331e669')

default_app = initialize_app()
db = firestore.client()

'''
동작 방식:
    1. 라인 callback()을 통해 사용자로부터 text를 받는다.
    2. hadler가 callback()으로부터 메시지를 받으면 이를 detect_intent_texts()에게 전달한다.
    3. detect_intent_texts()는 텍스트를 DialogFlow에 보내서, 해당 메시지가 어떤 Intent에 해당하고 어떤 parameter를 가지는지 등의 정보를 받는다.
    (이때 responses를 받을 수도 있지만 해당 response는 웹훅을 쓸 필요가 없기 때문에 설정된 response만 가능하다.)
    4. detect_intent_texts()를 이용해 어떤 Intent인지 확인되면 인텐트에 맞게 기능을 연결한다.
    (여기서는 Firebase FireCloud에 저장하는 것으로 한다.)
    5. 기능으로부터 결과값을 전달받으면 이를 핸들러에게 전달한다.
    6. 핸들러는 해당 결과값을 사용자에게 전달한다.
'''

@myapp.route("/")
def print_hello():
    return render_template('test.html')

#웹페이지에 정답을 firebase에 저장
@myapp.route("/submit", methods=['POST'])
def save_query_html():
    data = db.collection(u'test').document(request.form['id'])
    data.add({u'정답' : request.form['input']})
    # if(request.method=='GET'):
    #     return render_template('test.html')
    # elif(request.method=='POST'):
    #     return "정답은 임승찬입니다."
    return "시험제출 완료"

# 라인 연결 콜백 부분(거의 건들 일 없음) [1]
@myapp.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    log.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


# 라인 텍스트 response
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if (event.message.text == "시간"):
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(
                alt_text='Buttons template',
                template=ButtonsTemplate(
                    thumbnail_image_url='https://picsum.photos/300',
                    title='시간 테스트',
                    text='피커 구현',
                    actions=[
                        DatetimePickerAction(
                            label='datetime',
                            display_text='datetime',
                            data='datetime',
                            mode="datetime"
                        ),
                        URIAction(
                            label='uri',
                            uri='http://example.com/'
                        )
                    ]
                )
            ))
    else:
        # dialog 결과 전달 받기 [2]
        response = detect_intent_texts("test-dpu9", "connect_line", [event.message.text], "en-US")
        # 라인에 메세지 전달 [6]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response))


# Dialogflow 인텐트 인식(어떤 인텐트이고, 변수가 무엇인지만 판별.)
def detect_intent_texts(project_id, session_id, texts, language_code):
    """Returns the result of detect intent with texts as inputs.
    Using the same `session_id` between requests allows continuation
    of the conversation."""
    # 건들지 않아도 되는 부분 시작
    from google.cloud import dialogflow
    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)
    print('Session path: {}\n'.format(session))

    for text in texts:
        text_input = dialogflow.TextInput(
            text=text, language_code=language_code)

        query_input = dialogflow.QueryInput(text=text_input)

        response = session_client.detect_intent(
            request={'session': session, 'query_input': query_input})

        print('=' * 20)
        print('Query text: {}'.format(response.query_result.query_text))
        print('Detected intent: {} (confidence: {})\n'.format(
            response.query_result.intent.display_name,
            response.query_result.intent_detection_confidence))
        print('Fulfillment text: {}\n'.format(
            response.query_result.fulfillment_text))

        # 건들지 않아도 되는 부분 끝

        # 인텐트 이름 [3]
        intent_name = response.query_result.intent.display_name

        # 여기에서 intent_name에 따른 기능 분리 [4]
        if (intent_name == "WriteToFirestore"):
            res = save_query_by_parameters(response.query_result.parameters)  # [5]

        return res


# firebase에 entry 저장
def save_query_by_parameters(parameters):
    print("save {}".format(parameters.get('databaseEntry')))

    data = db.collection(u'dialogflow')

    data.add({
        u'entry': parameters.get('databaseEntry')
    })

    return u"save {}".format(parameters.get('databaseEntry'))



if __name__ == "__main__":
    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    # ssl_context.load_cert_chain(certfile='cert.pem', keyfile='key.pem', password='aa')
    # myapp.run(debug=True, host="0.0.0.0", port=5000, ssl_context=ssl_context)
    myapp.run(host="0.0.0.0")


