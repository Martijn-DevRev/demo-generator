"""
Author: Martijn Bosschaart (based on the work by Jae Hosking)
Description: GPT functions for trails, tickets and issues used in Objects.py.
Version: 0.1.1
"""
from openai import OpenAI
import json
import re
import random
import os
from pathlib import Path
import logging
from utils import save_payload_to_file

# Set up logging
logger = logging.getLogger(__name__)

def prompt_gpt_for_trails(company_url, openai_credentials, session_path):
    """
    Generate product trails structure using GPT and save to session directory
    Args:
        company_url: URL of the company website
        openai_credentials: Dictionary containing OpenAI credentials
        session_path: Path to session directory (required)
    Returns:
        Dictionary containing the trails structure
    """
    try:
        print("\n========================================")
        print("Phase 1: GPT Product Hierarchy Generation")
        print("========================================")
        logger.info(f"Starting product hierarchy generation for {company_url}")

        client = OpenAI(
            organization=openai_credentials["organization"],
            api_key=openai_credentials["api_key"]
        )

        messages = [
            {"role": "system", "content": """You have been trained on the information contained at https://docs.devrev.ai/product/parts to understand DevRev-specific terminology.
            Your task is to create and display visuals representing the hierarchy of a company's product by looking at it's website and create a detailed JSON output, following the structure:
            Capability, Feature, and Subfeature. Use public information for this visualization and always show the entire hierarchy without additional prompts.
            If specific data is unavailable, try to determine what type of business, service or product the site is about and use your imagination to create believable product details to construct the visualization.
            CRITICAL: You must return ONLY a valid JSON object. No other text, no explanations, no markdown.
            The response must be a perfect JSON object that can be parsed directly.
            You are to use the exact JSON format and pattern of:
            {
            "capability name": {
                "feature name": ["subfeature name"]
            }
            }
            IMPORTANT:
            1. Use only double quotes for JSON structure
            2. Return only the JSON object, nothing else
            3. Ensure all JSON syntax is valid
            4. Do not include any explanations or additional text"""},
            {"role": "user", "content": f"Visualize the detailed product hierarchy for {company_url} without placeholders."}
        ]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )

        print("\n========================================")
        print("Phase 2: Processing GPT Response")
        print("========================================")

        json_text = [choice.message.content for choice in response.choices if choice.message.content]
        if not json_text:
            raise Exception("No response content from GPT")

        logger.debug("\nRaw GPT response:")
        logger.debug(json_text[0])

        try:
            json_data = json.loads(json_text[0])
            if not isinstance(json_data, dict):
                raise ValueError(f"Expected dictionary for trails, got {type(json_data)}")

            save_payload_to_file(json_data, "trails_gpt", session_path)
            logger.info(f"Product hierarchy JSON created with {len(json_data)} capabilities")
            print("========================================")
            return json_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {json_text}")
            print("========================================")
            raise Exception("Invalid JSON response from GPT")

    except Exception as e:
        logger.error(f"Error in prompt_gpt_for_trails: {str(e)}")
        logger.debug(f"Raw response text: {json_text if 'json_text' in locals() else 'No response'}")
        print("========================================")
        raise

def prompt_gpt_for_tickets(parts, company_url, min_quantity, max_quantity, openai_credentials, session_path, progress_callback=None):
    """
    Generate ticket content using GPT and save to session directory
    Args:
        parts: Dictionary of parts information
        company_url: URL of the company website
        min_quantity: Minimum number of tickets per part
        max_quantity: Maximum number of tickets per part
        openai_credentials: Dictionary containing OpenAI credentials
        session_path: Path to session directory (required)
        progress_callback: Callback function for progress updates
    Returns:
        List of generated tickets
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Tickets: {message}", percent)

    tickets = []
    usage = 0
    severities_list = ', '.join(["low", "medium", "high", "blocker"])
    stages_list = ["resolved", "queued", "in_development", "awaiting_customer_response"]

    print("\n========================================")
    print("Phase 1: GPT Ticket Content Generation")
    print("========================================")
    logger.info(f"Starting ticket generation for {len(parts)} parts")

    if progress_callback:
        update_progress("Starting ticket generation...", 0)

    # Initialize OpenAI client
    client = OpenAI(
        organization=openai_credentials["organization"],
        project=openai_credentials["project"],
        api_key=openai_credentials["api_key"]
    )

    i = 1
    total_iterations = len(parts)
    expected_tickets = len(parts) * max_quantity
    current_tickets = 0

    for part in parts:
        number_of_tickets = random.randint(min_quantity, max_quantity)
        system_prompt = f"""You have been trained on all products from {company_url}. Your task is to create {number_of_tickets} support tickets for the part {part}. Each ticket must have:
- A descriptive title of approximately 10 words
- A relevant description of 80 words
- A severity level from this list: {severities_list}
- A stage from this list: {', '.join(stages_list)}
CRITICAL: You must return ONLY a valid JSON array. No other text, no explanations, no markdown.
The response must be a perfect JSON array that can be parsed directly.
Each ticket must exactly match this structure:
{{
"title": "Ticket Title",
"body": "Ticket Description",
"severity": "severity_level",
"stage": "stage_name"
}}
Example of valid response format:
[
{{
"title": "Example Ticket 1",
"body": "Description 1",
"severity": "low",
"stage": "queued"
}},
{{
"title": "Example Ticket 2",
"body": "Description 2",
"severity": "medium",
"stage": "in_development"
}}
]
IMPORTANT:
1. Use only double quotes for JSON structure
2. Include all required fields exactly as shown
3. Return only the JSON array, nothing else
4. Ensure all JSON syntax is valid"""

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create {number_of_tickets} support tickets for part {part} and provide the JSON output."}
            ],
            model="gpt-3.5-turbo",
        )

        usage = usage + response.usage.total_tokens
        logger.debug(f"\nRaw GPT response for {part}:")
        logger.debug(response.choices[0].message.content)

        try:
            response_tickets = json.loads(response.choices[0].message.content)
            for ticket in response_tickets:
                ticket["applies_to_part"] = part
                ticket["type"] = "ticket"
            tickets.extend(response_tickets)
            current_tickets += len(response_tickets)
        except Exception as e:
            logger.error(f"Failed to process tickets for part: {part}. Error: {str(e)}")
            continue

        # Show progress bar regardless of log level AND update GUI
        progress = (i / total_iterations) * 100
        print(f'\rProgress: [{int(progress)}%] {"#" * int(progress / 2)}', end='', flush=True)
        update_progress(f"Generating content for part {i}/{total_iterations}: {part}", progress)
        i += 1

    print("\n========================================")
    print("Phase 2: Processing Ticket Content")
    print("========================================")
    logger.info(f"Created {len(tickets)} tickets")
    logger.info(f"Total tokens used: {usage}")

    # Save generated tickets to session directory
    save_payload_to_file(tickets, "tickets_gpt", session_path)
    logger.info(f"Saved {len(tickets)} tickets to session directory")

    print("========================================")
    return tickets

def prompt_gpt_for_issues(parts, company_url, min_quantity, max_quantity, openai_credentials, session_path, progress_callback=None):
    """
    Generate issue content using GPT and save to session directory
    Args:
        parts: Dictionary of parts information
        company_url: URL of the company website
        min_quantity: Minimum number of issues per part
        max_quantity: Maximum number of issues per part
        openai_credentials: Dictionary containing OpenAI credentials
        session_path: Path to session directory (required)
        progress_callback: Callback function for progress updates
    Returns:
        List of generated issues
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Issues: {message}", percent)

    issues = []
    usage = 0
    priorities_list = ', '.join(["p3", "p2", "p1", "p0"])
    stages_list = ["triage", "in_development", "in_review", "completed"]

    print("\n========================================")
    print("Phase 1: GPT Issue Content Generation")
    print("========================================")
    logger.info(f"Starting issue generation for {len(parts)} parts")

    if progress_callback:
        update_progress("Starting issue generation...", 0)

    # Initialize OpenAI client
    client = OpenAI(
        organization=openai_credentials["organization"],
        project=openai_credentials["project"],
        api_key=openai_credentials["api_key"]
    )

    i = 1
    total_iterations = len(parts)
    expected_issues = len(parts) * max_quantity
    current_issues = 0

    for part in parts:
        number_of_issues = random.randint(min_quantity, max_quantity)
        system_prompt = f"""You have been trained on all products from {company_url}. Your task is to create {number_of_issues} engineering issues for the part {part}. Each issue must have:
- A descriptive title of approximately 10 words
- A relevant description of 80 words
- A priority level from this list: {priorities_list} (ordered from lowest to highest)
- A stage from this list: {', '.join(stages_list)}
CRITICAL: You must return ONLY a valid JSON array. No other text, no explanations, no markdown.
The response must be a perfect JSON array that can be parsed directly.
Each issue must exactly match this structure:
{{
"title": "Issue Title",
"body": "Issue Description",
"priority": "priority_level",
"stage": "stage_name"
}}
Example of valid response format:
[
{{
"title": "Example Issue 1",
"body": "Description 1",
"priority": "p2",
"stage": "triage"
}},
{{
"title": "Example Issue 2",
"body": "Description 2",
"priority": "p1",
"stage": "in_development"
}}
]
IMPORTANT:
1. Use only double quotes for JSON structure
2. Include all required fields exactly as shown
3. Return only the JSON array, nothing else
4. Ensure all JSON syntax is valid"""

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create {number_of_issues} engineering issues for part {part} and provide the JSON output."}
            ],
            model="gpt-3.5-turbo",
        )

        usage = usage + response.usage.total_tokens
        logger.debug(f"\nRaw GPT response for {part}:")
        logger.debug(response.choices[0].message.content)

        try:
            response_issues = json.loads(response.choices[0].message.content)
            for issue in response_issues:
                issue["applies_to_part"] = part
                issue["type"] = "issue"
            issues.extend(response_issues)
            current_issues += len(response_issues)
        except Exception as e:
            logger.error(f"Failed to process issues for part: {part}. Error: {str(e)}")
            continue

        # Show progress bar regardless of log level AND update GUI
        progress = (i / total_iterations) * 100
        print(f'\rProgress: [{int(progress)}%] {"#" * int(progress / 2)}', end='', flush=True)
        update_progress(f"Generating content for part {i}/{total_iterations}: {part}", progress)
        i += 1

    print("\n========================================")
    print("Phase 2: Processing Issue Content")
    print("========================================")
    logger.info(f"Created {len(issues)} issues")
    logger.info(f"Total tokens used: {usage}")

    # Save generated issues to session directory
    save_payload_to_file(issues, "issues_gpt", session_path)
    logger.info(f"Saved {len(issues)} issues to session directory")

    print("========================================")
    return issues
