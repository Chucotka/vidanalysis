import base64
import json
import openai
from backend.config import settings

def describe_scene(image_path: str, context: str):
    if settings.MOCK_AI:
        # Generate a varied mock tag based on the image path hash to be deterministic but varied
        tags = ["ACTION", "DIALOGUE", "CHASE", "EXPLOSION", "ROMANCE", "COMEDY", "DRAMA", "TRANSITION", "MONTAGE", "CREDITS"]
        import hashlib
        h = int(hashlib.md5(image_path.encode()).hexdigest(), 16)
        tag = tags[h % len(tags)]
        return {
            "description": f"Mock description for a scene classified as {tag}. Visually, characters are engaged in a {tag.lower()} sequence.",
            "tag": tag,
            "mood": "varied"
        }

    if not settings.OPENAI_API_KEY:
        return {
            "description": "Scene description unavailable.",
            "tag": "UNKNOWN",
            "mood": "unknown"
        }

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    prompt = (
        "You are a film analyst. Given this keyframe from a movie scene and its surrounding dialogue, "
        "write a concise 1-2 sentence description of: (1) what is happening visually, (2) who is "
        "speaking/present if identifiable, (3) the mood or tone. Be specific and factual.\n"
        "Return the output as JSON.\n\n"
        f"Context Dialogue: {context if context else 'No dialogue in this scene.'}"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        response_format={ "type": "json_object" },
        # Instruct the model to return JSON structure
        tools=[{
             "type": "function",
             "function": {
                 "name": "provide_scene_analysis",
                 "description": "Provide the analysis of the scene.",
                 "parameters": {
                     "type": "object",
                     "properties": {
                         "description": {"type": "string", "description": "1-2 sentence description"},
                         "tag": {"type": "string", "enum": ["DIALOGUE", "ACTION", "FIGHT", "CHASE", "EXPLOSION", "ROMANCE", "COMEDY", "DRAMA", "TRANSITION", "MONTAGE", "CREDITS", "SILENCE"]},
                         "mood": {"type": "string"}
                     },
                     "required": ["description", "tag", "mood"]
                 }
             }
        }],
        tool_choice={"type": "function", "function": {"name": "provide_scene_analysis"}}
    )

    try:
        args = response.choices[0].message.tool_calls[0].function.arguments
        return json.loads(args)
    except Exception as e:
        print(f"Error parsing GPT-4o response: {e}")
        return {
            "description": "Error generating description.",
            "tag": "UNKNOWN",
            "mood": "unknown"
        }
