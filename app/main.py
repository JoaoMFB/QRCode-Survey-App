# Import necessary libraries:
import os
import redis
import qrcode
import io
import base64
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Redis Connection ---
# Attempt to connect to the Redis server. This block ensures the app can handle a connection failure gracefully.
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True
    )
    redis_client.ping()
    print(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    redis_client = None


# --- Data Model in Redis ---
# Key: "survey:{survey_id}"
# Value: A Redis Hash
#   - "question": The text of the question.
#   - "yes": Number of yes votes.
#   - "no": Number of no votes.
#
# Key: "next_survey_id"
# Value: A simple String used as an atomic counter to generate unique IDs for new surveys.

# --- Endpoint 1: The Homepage ---

@app.get("/", response_class=HTMLResponse)
async def show_create_form(request: Request):
    """
    Handles GET requests to the root URL ("/").
    Displays the main page with the survey creation form and a history of past surveys.
    """
    if not redis_client:
        return HTMLResponse("Error: Redis is not connected.", status_code=500)

    surveys_history = []
    # Get all keys from Redis that match the pattern "survey:*". This is how we find all surveys.
    survey_keys = redis_client.keys("survey:*")

    for key in survey_keys:
        try:
            # Extract the numeric ID from the key string (e.g., "survey:5" -> 5).
            survey_id = int(key.split(":")[1])
            # Retrieve just the "question" field from the Hash associated with the key.
            question = redis_client.hget(key, "question")
            if question:
                surveys_history.append({"id": survey_id, "question": question})
        except (IndexError, ValueError):
            # Safely ignore keys that don't match the expected format.
            continue
    
    # Sort the surveys by their ID to ensure a consistent order.
    surveys_history.sort(key=lambda x: x['id'])

    # Render the HTML template, passing the request object and the list of surveys.
    response = templates.TemplateResponse("create_survey.html", {
        "request": request,
        "surveys": surveys_history
    })

    # Add headers to the response to prevent the browser from caching this page.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

# --- Endpoint 2: Creating a Survey ---

@app.post("/create", response_class=HTMLResponse)
async def handle_create_survey(request: Request, question: str = Form(...)):
    """
    Handles POST requests from the survey creation form.
    """
    if not redis_client:
        return HTMLResponse("Error: Redis is not connected.", status_code=500)

    # 1. Get a new unique ID by atomically incrementing our counter key in Redis.
    survey_id = redis_client.incr("next_survey_id")

    # 2. Store the new survey in Redis using a Hash data structure.
    redis_client.hset(f"survey:{survey_id}", mapping={
        "question": question,
        "yes": 0,
        "no": 0
    })

    # 3. Generate the full URLs for voting and results.
    # `request.base_url` makes the links work correctly whether accessed via localhost or an IP address.
    base_url = str(request.base_url)
    vote_url = f"{base_url}vote/{survey_id}"
    results_url = f"{base_url}results/{survey_id}"

    # Generate the QR code image in memory, not as a file.
    qr_img = qrcode.make(vote_url)
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    # Encode the image bytes into a Base64 string, which can be embedded directly in an HTML <img> tag.
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # 4. Render the result page, passing all the generated data to the template.
    return templates.TemplateResponse("creation_result.html", {
        "request": request,
        "question": question,
        "qr_code_img": img_str,
        "vote_url": vote_url,
        "results_url": results_url
    })

# --- Endpoint 3: Voting ---

@app.get("/vote/{survey_id}", response_class=HTMLResponse)
async def show_vote_page(request: Request, survey_id: int):
    """Displays the voting page for a specific survey."""
    if not redis_client:
        return HTMLResponse("Error: Redis is not connected.", status_code=500)

    question = redis_client.hget(f"survey:{survey_id}", "question")
    if not question:
        return HTMLResponse("Survey not found.", status_code=404)

    return templates.TemplateResponse("vote.html", {
        "request": request,
        "survey_id": survey_id,
        "question": question
    })

@app.post("/vote/{survey_id}")
async def handle_vote(survey_id: int, vote: str = Form(...)):
    """Handles the submission of a 'Yes' or 'No' vote."""
    if not redis_client:
        return HTMLResponse("Error: Redis is not connected.", status_code=500)

    if vote.lower() == "yes":
        redis_client.hincrby(f"survey:{survey_id}", "yes", 1)
    elif vote.lower() == "no":
        redis_client.hincrby(f"survey:{survey_id}", "no", 1)

    # Redirect the user to the results page. This is the Post-Redirect-Get (PRG) pattern.
    # It prevents duplicate votes if the user refreshes the page.
    return RedirectResponse(url=f"/results/{survey_id}", status_code=303)

# --- Endpoint 4: Viewing Results ---

@app.get("/results/{survey_id}", response_class=HTMLResponse)
async def show_results_page(request: Request, survey_id: int):
    """Displays the results of a survey."""
    if not redis_client:
        return HTMLResponse("Error: Redis is not connected.", status_code=500)

    # Retrieve all fields and values for the survey's Hash in one command.
    survey_data = redis_client.hgetall(f"survey:{survey_id}")
    if not survey_data:
        return HTMLResponse("Survey not found.", status_code=404)

    # Extract the data from the dictionary returned by Redis.
    question = survey_data.get("question", "N/A")
    yes_votes = int(survey_data.get("yes", 0))
    no_votes = int(survey_data.get("no", 0))
    total_votes = yes_votes + no_votes

    # Calculate percentages for the bar chart, safely handling the case of zero total votes.
    yes_percent = (yes_votes / total_votes * 100) if total_votes > 0 else 0
    no_percent = (no_votes / total_votes * 100) if total_votes > 0 else 0

    return templates.TemplateResponse("results.html", {
        "request": request,
        "question": question,
        "yes_votes": yes_votes,
        "no_votes": no_votes,
        "total_votes": total_votes,
        "yes_percent": yes_percent,
        "no_percent": no_percent
    })

# --- Endpoint 5: Clearing History ---

@app.post("/clear-history")
async def handle_clear_history():
    """Deletes all survey-related data from Redis."""
    if not redis_client:
        return HTMLResponse("Error: Redis is not connected.", status_code=500)

    # Find all keys related to the survey app.
    survey_keys = redis_client.keys("survey:*")
    if survey_keys:
        # Delete all survey hashes in a single command. The * unpacks the list.
        redis_client.delete(*survey_keys)
    
    # Also reset the main counter.
    redis_client.delete("next_survey_id")

    # Redirect the user back to the home page using the PRG pattern.
    return RedirectResponse(url="/", status_code=303)


