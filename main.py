import os
import requests
import json
import anthropic
from dotenv import load_dotenv

# loading keys
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
LLM_API_KEY = os.getenv("LLM_API_KEY")


if not TMDB_API_KEY or not LLM_API_KEY:
    raise EnvironmentError("Set API keys in .env file: TMDB_API_KEY and LLM_API_KEY")

# setting up the LLM
client = anthropic.Anthropic(api_key=LLM_API_KEY)

# TMDB-API URL
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Load system prompt from `system_prompt.txt`
SYSTEM_PROMPT = ""
try:
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
        if SYSTEM_PROMPT:
            SYSTEM_PROMPT += "\n\n"
        else:
            raise ValueError("`system_prompt.txt` is empty")
except FileNotFoundError:
    raise FileNotFoundError("Create `system_prompt.txt` in the project root!")
except Exception as e:
    raise RuntimeError(f"Failed to load system prompt: {e}")



# Simple calls
def handle_get_popular_movies():
    print("[handle_get_popular_movies running]")
    try:
        params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
            "page": 1
        }
        response = requests.get(f"{TMDB_BASE_URL}/movie/popular", params=params)
        response.raise_for_status()

        movies = response.json().get("results", [])

        movie_list = [f"- {movie['title']} (Rating: {movie['vote_average']})" for movie in movies[:5]]
        return "The top 5 popular movies now:\n" + "\n".join(movie_list)

    except requests.RequestException as e:
        return f"Error during API call: {e}"


# Composite calls
def handle_get_movie_details(movie_name):
    print(f"[handle_get_movie_details running, searching: '{movie_name}']")
    try:
        # Search for movie ID by name
        search_params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
            "query": movie_name
        }
        search_response = requests.get(f"{TMDB_BASE_URL}/search/movie", params=search_params)
        search_response.raise_for_status()

        results = search_response.json().get("results", [])
        if not results:
            return f"No movie titled '{movie_name}'."

        movie_id = results[0]["id"]
        print(f"[Found, movie ID: {movie_id}]")

        # Get movie details by ID
        details_params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US"
        }
        details_response = requests.get(f"{TMDB_BASE_URL}/movie/{movie_id}", params=details_params)
        details_response.raise_for_status()

        details = details_response.json()

        return (
            f"Details of '{details['title']}' movie:\n"
            f"Overview: {details['overview']}\n"
            f"Vote average: {details['vote_average']}/10\n"
            f"Release date: {details['release_date']}"
        )

    except requests.RequestException as e:
        return f"Error during API call: {e}"


def handle_get_actor_credits(actor_name):
    print(f"[handle_get_actor_credits running, searching: '{actor_name}']")
    try:
        # Search for actor ID by name
        search_params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
            "query": actor_name
        }
        search_response = requests.get(f"{TMDB_BASE_URL}/search/person", params=search_params)
        search_response.raise_for_status()

        results = search_response.json().get("results", [])
        if not results:
            return f"No actor named '{actor_name}'."

        person_id = results[0]["id"]
        print(f"[Found, actor ID: {person_id}]")

        # Get actor movie credits by ID
        credits_params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US"
        }
        credits_response = requests.get(f"{TMDB_BASE_URL}/person/{person_id}/movie_credits", params=credits_params)
        credits_response.raise_for_status()

        credits = credits_response.json().get("cast", [])

        top_movies = sorted(credits, key=lambda x: x.get("popularity", 0), reverse=True)[:5]
        movie_list = [f"- {movie['title']} (Character: {movie['character']})" for movie in top_movies]

        return f"'{actor_name}' (ID: {person_id})'s top movies:\n" + "\n".join(movie_list)

    except requests.RequestException as e:
        return f"Error during API call: {e}"



# LLM call to get intent
def get_intent_from_llm(user_text):

    try:
        response = client.messages.create(
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages= [
                {"role": "user", "content": user_text},
            ],
            model="claude-3-5-haiku-latest"
        )

        json_str = response.text.strip().replace("```json", "").replace("```", "").strip()

        print(f"[Raw response]: {json_str}")

        # JSON parsing
        intent_data = json.loads(json_str)
        return intent_data

    except json.JSONDecodeError:
        print(f"LLM response was not a JSON: {response.text}")
        return {"function_name": "unsupported_request", "parameters": {}}
    except Exception as e:
        print(f"LLM call failed: {e}")
        return {"function_name": "unsupported_request", "parameters": {}}



# Main application loop
def main():
    print("This assistant can help you with movie-related queries using TMDB data.\nYou can ask about popular movies, movie details, and actor credits.\nQuit by typing 'quit'.")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == "quit":
            break

        # Get intent from LLM
        intent = get_intent_from_llm(user_input)

        function_name = intent.get("function_name")
        parameters = intent.get("parameters", {})

        print(f"Intent: {function_name}, Parameters: {parameters}")

        # Call appropriate handler based on intent
        if function_name == "get_popular_movies":
            response_text = handle_get_popular_movies()

        elif function_name == "get_movie_details":
            if "movie_name" in parameters:
                response_text = handle_get_movie_details(parameters["movie_name"])
            else:
                response_text = "LLM could not extract the movie name."

        elif function_name == "get_actor_credits":
            if "actor_name" in parameters:
                response_text = handle_get_actor_credits(parameters["actor_name"])
            else:
                response_text = "LLM could not extract the actor name."

        elif function_name == "unsupported_request":
            response_text = "This request is not supported. Please ask about popular movies, movie details, or actor credits."

        else:
            response_text = f"No function called '{function_name}'."

        # Respond to user
        print(f"\nAssistant: {response_text}")


if __name__ == "__main__":
    main()