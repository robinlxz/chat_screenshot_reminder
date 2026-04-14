import base64
import json
import logging
from openai import AsyncOpenAI
from src.config import API_KEY, BASE_URL, MODEL_NAME

logger = logging.getLogger(__name__)

# Initialize OpenAI async client
client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

async def extract_reminder_info(image_path: str) -> dict:
    """
    Extracts time and content from a chat screenshot using Vision LLM.
    Returns a dict with 'extracted_text' and 'reminder_time' (ISO format).
    """
    if not API_KEY:
        logger.warning("API_KEY is not set. Returning mock data.")
        return {
            "extracted_text": "Mock extracted text from image.",
            "reminder_time": None # Will be handled by caller
        }

    try:
        base64_image = encode_image(image_path)
        
        prompt = """
        Analyze this chat screenshot and extract the most important information that needs a reminder.
        
        Specifically, please identify:
        1. The Chat Group Name or Title (if visible, e.g., at the top header).
        2. The core request, question, or action item mentioned in the chat.
        IMPORTANT: If there are multiple questions or messages in the screenshot, focus ONLY on identifying and extracting the LAST (bottom-most) question or action item in the conversation thread.
        
        Please return a JSON object with the following keys:
        - "extracted_text": A clear summary. Format it like: "[Group Name] Sender asks: ..." or include specific details (e.g., "UID XXXXX requires CDN activation").
        - "reminder_time": The specific time mentioned in the format "YYYY-MM-DDTHH:MM:SS" (string, ISO 8601). If no explicit date/time is mentioned, return null.
        
        ONLY output valid JSON. Do not include any other text or markdown formatting.
        """
        
        response = await client.chat.completions.create(
            model=MODEL_NAME,
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
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        logger.info(f"[LLM Extraction] Image: {image_path} -> Result: {json.dumps(result, ensure_ascii=False)}")
        
        return {
            "extracted_text": result.get("extracted_text", "No text extracted"),
            "reminder_time": result.get("reminder_time", None)
        }
    except Exception as e:
        logger.error(f"Error calling Vision API: {e}")
        return {
            "extracted_text": f"⚠️ AI Parsing Failed: {str(e)}",
            "reminder_time": None
        }
