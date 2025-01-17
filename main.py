import firebase_admin
from firebase_admin import credentials, storage
from google.cloud import aiplatform
from flask import Flask, request, jsonify
import os
import base64
import uuid

# Initialize Flask app
app = Flask(__name__)


def initialize_firebase():
    """Initializes Firebase Admin SDK."""
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(
            os.path.join(os.path.dirname(__file__), "ndou-dev-test-83775e3696cf.json")
        )  # Path to your key inside 'backend'
        firebase_admin.initialize_app(cred,
        {'storageBucket':'ndou-dev-test.appspot.com'}
        )

def upload_image(file):
    """Uploads image to Firebase Storage and returns public URL"""
    bucket = storage.bucket()
    blob_name = f"user_images/{str(uuid.uuid4())}-{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file)

    public_url = blob.generate_signed_url(
        version="v4",
         expiration=None,
         method="GET"
      )
    return public_url

def call_gemini_api(image_data):
  """Calls the Gemini API to extract text from image data"""
  aiplatform.init(project="ndou-dev-test", location="us-central1") # Replace with your project and location

  model = aiplatform.GenerativeModel("gemini-pro-vision") #Use correct name for your project
  prompt = "Extract all relevant information from the document"

  contents = [
      {
      "parts": [
              {"text": prompt},
            {
                "inline_data": {
                   "data":base64.b64encode(image_data).decode("utf-8"),
                   "mime_type": "image/png"
                  }
               },
              ],
      }
  ]

  response = model.generate_content(contents=contents)

  return response.text


html_form = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hand-Completed Log Reader</title>
    <style>
         body {
           font-family: sans-serif;
           margin: 2em auto;
           padding: 0 1em;
           max-width: 800px;
           line-height: 1.6;
        }

        main {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 8px;
        }

        h1 {
            text-align: center;
            margin-bottom: 1.5em;
        }

        .image-picker {
            margin-bottom: 1em;
           text-align: center;
       }

        .image-picker input[type="file"] {
           display: block;
           width: 100%;
           padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 1rem;
            cursor: pointer;
        }

       .prompt-box {
            text-align: center;
           margin-bottom: 1em;
        }

        .prompt-box button {
           padding: 10px 20px;
           background-color: #4caf50;
            color: white;
            border: none;
          border-radius: 5px;
           cursor: pointer;
           font-size: 1rem;
       }

       .prompt-box button:hover {
            background-color: #3d8b40;
       }

       p.output {
            white-space: pre-wrap;
           margin-top: 1em;
           padding: 10px;
          border: 1px solid #eee;
           border-radius: 5px;
        }
    </style>
</head>
<body>
    <main>
        <h1>Read Hand-Completed Logs with the Gemini API</h1>
        <form action="/api/extract-info" method="POST" enctype="multipart/form-data">
            <div class="image-picker">
                <label class="">
                    <input type="file" name="images" id="chosen-image" accept="image/*" multiple required>
                </label>
            </div>
            <div class="prompt-box">
                <button type="submit">Go</button>
            </div>
        </form>
         <p class="output">
             {}
         </p>
    </main>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    return html_form.format('')


@app.route('/api/extract-info', methods=['POST'])
def extract_info():
    initialize_firebase()

    if 'images' not in request.files:
        return html_form.format('No images uploaded'), 400

    uploaded_files = request.files.getlist('images')

    if not uploaded_files:
        return html_form.format('No file selected'), 400

    extracted_texts = []
    for image_file in uploaded_files:
        try:
            # Upload image to firebase
            url = upload_image(image_file)
            # Get contents of the file
            image_file.seek(0)
            image_data = image_file.read()
            # Call Gemini to extract the data
            extracted_text = call_gemini_api(image_data)
            extracted_texts.append(extracted_text)
        except Exception as e:
            print(e)
            return html_form.format(f'Error processing image: {e}'), 500

    return html_form.format('\n'.join(extracted_texts))


if __name__ == '__main__':
   app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
