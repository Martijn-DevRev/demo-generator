"""
Core functionality for DevRev object manipulation.
Contains all object-related functions and utilities.
"""
import requests
import pandas as pd
import json
import random
import sys
from pathlib import Path
from GPT import *
import os
import logging
from utils import save_payload_to_file

# Set up logging
logger = logging.getLogger(__name__)

def load_objects(PAT, base_url, object_type, session_path=None):
    """
    Load objects from DevRev API and optionally save to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        object_type: Type of object to load
        session_path: Path to session directory
    Returns:
        List of loaded objects
    """
    objects = []
    api_url = base_url + object_type + ".list"
    
    # Check object type and set API parameters accordingly
    if "." not in object_type:
        object_type = object_type if "-" not in object_type else object_type.replace("-", "_")
    else:
        object_type = "result"  # For custom stages
    
    cursor_selector = "next_cursor" if object_type != "result" else "cursor"
    cursor = ""
    
    while cursor != "end":
        headers = {
            'Authorization': f'Bearer {PAT}',
            'Content-Type': 'application/json'
        }
        params = {'cursor': cursor} if cursor else {}
        
        try:
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            for object in response.json()[object_type]:
                objects.append(object)
            cursor = response.json().get(cursor_selector, "end")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error loading objects with exception: {e}")
            logger.error(response.json())
            raise

    # Save loaded objects to session directory if provided
    if session_path and objects:
        # Use a more specific name for custom stages
        file_name = "custom_stages" if object_type == "result" else object_type
        save_payload_to_file(objects, f"{file_name}_loaded", session_path)

    return objects

def delete_objects(PAT, base_url, object_type, objects, progress_callback=None, base_progress=0, step_weight=20):
    """
    Delete objects from DevRev
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        object_type: Type of object to delete
        objects: List of object IDs to delete
        progress_callback: Callback function for progress updates
        base_progress: Base progress percentage
        step_weight: Weight of this step in overall progress
    Returns:
        List of failed deletions
    """
    print(f"\nDeleting {len(objects)} {object_type}...")
    total_iterations = len(objects)
    failed_deletions = []

    for i in range(total_iterations):
        headers = {
            'Authorization': f'Bearer {PAT}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(
                base_url + object_type + ".delete",
                headers=headers,
                json={"id": objects[i]}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            failed_deletions.append({"id": objects[i], "error": str(e)})
            print(f"\nError deleting {object_type} {objects[i]}: {str(e)}")

        # Calculate and display progress
        progress = (i + 1) / total_iterations * 100
        progress_bar_length = 50
        filled_length = int(progress_bar_length * (i + 1) // total_iterations)
        bar = '=' * filled_length + '-' * (progress_bar_length - filled_length)
        print(f'\rProgress: [{bar}] {progress:.1f}% | {i + 1}/{total_iterations} {object_type}', end='', flush=True)

        # Report progress to callback if provided
        if progress_callback:
            # Calculate overall progress for this step
            step_progress = base_progress + (progress * step_weight / 100)
            progress_callback(f"Deleting {object_type} ({i + 1}/{total_iterations})", step_progress)

    print()  # New line after progress bar
    
    # Report any failures
    if failed_deletions:
        print(f"\nFailed to delete {len(failed_deletions)} {object_type}:")
        for failure in failed_deletions:
            print(f"ID: {failure['id']} - Error: {failure['error']}")
    else:
        print(f"\nSuccessfully deleted all {object_type}")

    return failed_deletions
    
def post_objects(PAT, base_url, object_type, payloads):
    """
    Post objects to DevRev API
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        object_type: Type of object to create
        payloads: List of payload dictionaries
    Returns:
        List of response objects
    """
    api_url = base_url + object_type + ".create"
    responses = []
    
    for payload in payloads:
        headers = {
            'Authorization': f'Bearer {PAT}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            # Handle 409 Conflict for accounts
            if response.status_code == 409 and object_type == "accounts":
                print("\nAccount already exists, fetching existing accounts...")
                accounts, _ = get_accounts(PAT, base_url)
                return accounts

            response.raise_for_status()
            responses.append(response.json())
        except requests.exceptions.RequestException as e:
            if response.status_code == 409 and object_type == "accounts":
                continue
            else:
                print(f"\nError creating {object_type} with exception: {e}")
                print(response.json())
                raise

    return responses

def create_devusers(PAT, base_url, session_path=None, progress_callback=None):
    """
    Create dev users and save both payloads and responses to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        List of dev user IDs
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"DevUsers: {message}", percent)

    try:
        print("\n========================================")
        print("Creating Dev Users")
        print("========================================")
        update_progress("Loading user data...", 0)

        # Create and save payload
        dev_user_payloads = create_dev_user_payload()
        save_payload_to_file(dev_user_payloads, "devusers", session_path)
        
        total_users = len(dev_user_payloads)
        update_progress(f"Preparing {total_users} dev users...", 20)

        responses = []
        for idx, payload in enumerate(dev_user_payloads, 1):
            response = post_objects(PAT, base_url=base_url, object_type="dev-users", payloads=[payload])
            responses.extend(response)
            
            current_progress = 40 + ((idx/total_users) * 60)
            update_progress(f"Creating dev users ({idx}/{total_users})", current_progress)
            logger.info(f"Created dev user: {payload['full_name']}")

        # Save responses
        if responses:
            save_payload_to_file(responses, "devusers_responses", session_path)

        dev_user_ids = [response['dev_user']['id'] for response in responses]
        update_progress(f"Successfully created {len(dev_user_ids)} dev users", 100)
        print("========================================")
        return dev_user_ids

    except Exception as e:
        update_progress(f"Error creating dev users: {str(e)}", 0)
        raise

def create_dev_user_payload():
    """
    Create dev users payload from CSV
    Returns:
        List of dev user payloads
    """
    df = pd.read_csv('./data/common_input/dev_users.csv')
    json_payload = []
    
    for index, row in df.iloc[0:].iterrows():
        payload = {
            "email": f"{row['full_name'].lower().replace(' ', '.')}@example.co",
            "full_name": row['full_name'],
            "state": "shadow"
        }
        json_payload.append(payload)

    return json_payload

def create_accounts(PAT, base_url, dev_users, session_path=None, progress_callback=None):
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Accounts: {message}", percent)

    try:
        print("\n========================================")
        print("Creating Company Accounts")
        print("========================================")
        update_progress("Preparing account data...", 0)

        logger.info(f"Creating accounts with session path: {session_path}")  # Debug log

        # Create payload
        accounts_payload = create_accounts_payload(dev_users)
        
        # Save initial payload to session directory
        if session_path:
            save_payload_to_file(accounts_payload, "accounts", session_path)
            logger.info(f"Saved initial payload to session directory: {session_path}")
        else:
            logger.error("No session path provided to create_accounts!")
        
        total_accounts = len(accounts_payload)
        update_progress(f"Preparing {total_accounts} accounts...", 20)

        responses = []
        existing_accounts_found = False

        for idx, payload in enumerate(accounts_payload, 1):
            current_progress = 40 + ((idx/total_accounts) * 60)
            update_progress(f"Creating account ({idx}/{total_accounts})", current_progress)

            try:
                response = requests.post(
                    base_url + "accounts.create",
                    headers={
                        'Authorization': f'Bearer {PAT}',
                        'Content-Type': 'application/json'
                    },
                    json=payload
                )
                if response.status_code == 409:
                    logger.info(f"Account already exists: {payload['display_name']}")
                    existing_accounts_found = True
                    continue
                response.raise_for_status()
                responses.append(response.json())
                logger.info(f"Created account: {payload['display_name']}")
            except requests.exceptions.RequestException as e:
                if response.status_code != 409:
                    logger.error(f"Error creating account: {str(e)}")
                    raise

        # Save responses to session directory
        if responses and session_path:
            save_payload_to_file(responses, "accounts_responses", session_path)
            logger.info(f"Saved responses to session directory: {session_path}")

        # Process responses into accounts
        accounts = [
            {
                'name': str(response['account']['display_name']),
                'id': str(response['account']['id']),
                'display_id': str(response['account']['display_id']),
                'rev_org': {
                    'name': str(response["default_rev_org"]['display_name']),
                    'id': str(response["default_rev_org"]['id']),
                    'display_id': str(response["default_rev_org"]['display_id'])
                }
            } for response in responses
        ]

        # Save processed data to session directory
        if session_path:
            save_payload_to_file(accounts, "accounts_processed", session_path)
            logger.info(f"Saved processed data to session directory: {session_path}")

        update_progress(f"Created {len(accounts)} accounts", 100)
        print("========================================")
        return [accounts, [acc['rev_org'] for acc in accounts]]

    except Exception as e:
        update_progress(f"Error with accounts: {str(e)}", 0)
        raise

def create_accounts_payload(dev_users, session_path=None):
    """
    Create accounts payload from CSV and save to session directory
    Args:
        dev_users: List of developer user IDs
        session_path: Path to session directory
    Returns:
        List of account payloads
    """
    df = pd.read_csv('./data/common_input/accounts.csv')
    json_payload = []
    
    for index, row in df.iterrows():
        payload = {
            "display_name": str(row["name"]),
            "external_refs": [str(row["name"])],
            "owned_by": [random.choice(dev_users)]
        }
        json_payload.append(payload)

    # Save initial payload to session input directory
    if session_path:
        save_payload_to_file(json_payload, "accounts", session_path)

    return json_payload

def create_revusers(PAT, base_url, rev_orgs, session_path=None, progress_callback=None):
    """
    Create customer users and save both payloads and responses to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        rev_orgs: List of rev org information
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        List of customer user IDs
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"RevUsers: {message}", percent)

    try:
        print("\n========================================")
        print("Creating Customer Users")
        print("========================================")
        update_progress("Loading customer user data...", 0)

        # Get payload and let create_rev_user_payload handle the input file saving
        rev_users_payload = create_rev_user_payload(rev_orgs, session_path)
        total_users = len(rev_users_payload)
        update_progress(f"Preparing {total_users} customer users...", 20)

        responses = []
        failed_users = []
        
        for idx, payload in enumerate(rev_users_payload, 1):
            current_progress = 40 + ((idx/total_users) * 60)
            update_progress(f"Creating customer user ({idx}/{total_users})", current_progress)

            try:
                response = post_objects(PAT, base_url=base_url, object_type="rev-users", payloads=[payload])
                responses.extend(response)
                logger.info(f"Created customer user: {payload['display_name']}")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Customer user already exists: {payload['display_name']}")
                    failed_users.append({"user": payload['display_name'], "reason": "already exists"})
                    continue
                else:
                    logger.error(f"Error creating customer user: {payload['display_name']}")
                    failed_users.append({"user": payload['display_name'], "reason": str(e)})
                    continue

        # Save failed users to output_files if any
        if failed_users:
            save_payload_to_file(failed_users, "revusers_failed", session_path)

        # If we didn't create any new users, get existing ones
        if not responses:
            logger.info("Using existing rev-users")
            existing_users = get_revusers(PAT, base_url)
            
            # Save existing users to output_files
            save_payload_to_file(existing_users, "revusers_existing", session_path)
            
            rev_user_ids = [user['id'] for user in existing_users]
            update_progress(f"Using {len(rev_user_ids)} existing customer users", 100)
            print("========================================")
            return rev_user_ids

        # Save successful responses to output_files
        if responses:
            save_payload_to_file(responses, "revusers_responses", session_path)

        # Process and save successful users
        successful_users = [{
            'id': response['rev_user']['id'],
            'display_name': response['rev_user']['display_name'],
            'rev_org': response['rev_user']['rev_org']
        } for response in responses]
        
        # Save processed data to output_files
        save_payload_to_file(successful_users, "revusers_processed", session_path)

        rev_user_ids = [response['rev_user']['id'] for response in responses]
        update_progress(f"Successfully created {len(rev_user_ids)} customer users", 100)
        print("========================================")
        return rev_user_ids

    except Exception as e:
        update_progress(f"Error creating customer users: {str(e)}", 0)
        raise

def create_rev_user_payload(rev_orgs, session_path=None):
    """
    Create rev-user payload from CSV and save to session directory
    Args:
        rev_orgs: List of rev org information
        session_path: Path to session directory
    Returns:
        List of rev-user payloads
    """
    df = pd.read_csv('./data/common_input/rev_users.csv')
    json_payload = []
    
    for index, row in df.iterrows():
        rev_org = random.choice(rev_orgs)['id']
        payload = {
            "display_name": str(row["display_name"]),
            "rev_org": rev_org
        }
        json_payload.append(payload)

    # Save initial payload to session input directory
    if session_path:
        save_payload_to_file(json_payload, "revusers", session_path)

    return json_payload

def create_trails(PAT, company_url, dev_users, base_url, openai_credentials, session_path=None, progress_callback=None):
    """
    Create product hierarchy trails and save to session directory
    Args:
        PAT: DevRev PAT
        company_url: URL of the company website
        dev_users: List of developer user IDs
        base_url: Base URL for API
        openai_credentials: Dictionary containing OpenAI credentials
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        Dictionary of created parts
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Product Hierarchy: {message}", percent)

    try:
        update_progress("Initializing GPT prompt...", 0)
        trails_json = {}
        parts = {}
        gpt_retries = 0

        # Get trails from GPT and save to session directory
        while len(trails_json) == 0:
            try:
                update_progress("Prompting ChatGPT for product structure...", 5)
                trails_json = prompt_gpt_for_trails(company_url, openai_credentials, session_path)
            except Exception as e:
                gpt_retries += 1
                update_progress(f"GPT attempt {gpt_retries}/3 failed, retrying...", 5)
                if gpt_retries == 3:
                    raise Exception("GPT failed to return a response after 3 attempts")

        # Save initial trails structure
        save_payload_to_file(trails_json, "trails_gpt", session_path)

        total_capabilities = len(trails_json)
        total_items = 0
        for cap in trails_json:
            total_items += 1  # Capability
            total_items += len(trails_json[cap])  # Features
            for feature in trails_json[cap]:
                if isinstance(trails_json[cap][feature], list):
                    total_items += len(trails_json[cap][feature])  # Subfeatures

        update_progress(f"Preparing to create {total_items} total items...", 10)
        current_item = 0
        base_progress = 10
        progress_per_item = 80 / total_items

        print("\n========================================")
        print("Creating Product Hierarchy in DevRev")
        print("========================================")

        # Track all created items for saving
        created_items = {
            "capabilities": [],
            "features": [],
            "subfeatures": []
        }

        # Create Capabilities
        for capability in trails_json:
            current_item += 1
            update_progress(
                f"Creating capability ({current_item}/{total_capabilities}): {capability}",
                base_progress + (current_item * progress_per_item)
            )

            capability_payload = {
                "name": capability,
                "type": "capability",
                "owned_by": [random.choice(dev_users)],
                "parent_part": ["PROD-1"]
            }

            capability_post_response = post_objects(
                PAT,
                base_url=base_url,
                object_type="parts",
                payloads=[capability_payload]
            )

            caplPart = capability_post_response[0]["part"]
            parts.update({
                caplPart["name"]: {
                    "id": caplPart["id"],
                    "type": caplPart["type"],
                    "owned_by": caplPart["owned_by"][0]["id"]
                }
            })
            created_items["capabilities"].append(capability_post_response[0])
            logger.info(f"Created capability: {capability}")

            # Create Features for this Capability
            feature_count = len(trails_json[capability])
            for feature_idx, feature in enumerate(trails_json[capability], 1):
                current_item += 1
                update_progress(
                    f"Creating feature {feature_idx}/{feature_count} for {capability}: {feature}",
                    base_progress + (current_item * progress_per_item)
                )

                feature_payload = {
                    "name": feature,
                    "type": "feature",
                    "owned_by": [random.choice(dev_users)],
                    "parent_part": [capability_post_response[0]["part"]["id"]]
                }

                feature_post_response = post_objects(
                    PAT,
                    base_url=base_url,
                    object_type="parts",
                    payloads=[feature_payload]
                )

                featPart = feature_post_response[0]["part"]
                parts.update({
                    featPart["name"]: {
                        "id": featPart["id"],
                        "type": featPart["type"],
                        "owned_by": featPart["owned_by"][0]["id"]
                    }
                })
                created_items["features"].append(feature_post_response[0])
                logger.info(f"Created feature: {feature}")

                # Create Subfeatures for this Feature
                if isinstance(trails_json[capability][feature], list):
                    subfeature_count = len(trails_json[capability][feature])
                    for subfeature_idx, subfeature in enumerate(trails_json[capability][feature], 1):
                        current_item += 1
                        update_progress(
                            f"Creating subfeature {subfeature_idx}/{subfeature_count} for {feature}: {subfeature}",
                            base_progress + (current_item * progress_per_item)
                        )

                        subfeature_payload = {
                            "name": subfeature,
                            "type": "feature",
                            "owned_by": [random.choice(dev_users)],
                            "parent_part": [feature_post_response[0]["part"]["id"]]
                        }

                        subfeature_post_response = post_objects(
                            PAT,
                            base_url=base_url,
                            object_type="parts",
                            payloads=[subfeature_payload]
                        )

                        subfeatPart = subfeature_post_response[0]["part"]
                        parts.update({
                            subfeatPart["name"]: {
                                "id": subfeatPart["id"],
                                "type": subfeatPart["type"],
                                "owned_by": subfeatPart["owned_by"][0]["id"]
                            }
                        })
                        created_items["subfeatures"].append(subfeature_post_response[0])
                        logger.info(f"Created subfeature: {subfeature}")

        # Save all created items to session directory
        save_payload_to_file(created_items, "trails_responses", session_path)
        save_payload_to_file(parts, "parts", session_path)

        update_progress(f"Created {len(parts)} total parts successfully", 100)
        print("========================================")
        return parts

    except Exception as e:
        update_progress(f"Error creating product hierarchy: {str(e)}", 0)
        raise

def create_tickets(PAT, base_url, company_url, min_tickets_per_part, max_tickets_per_part, stages, parts, rev_orgs, openai_credentials, session_path=None, progress_callback=None):
    """
    Create tickets and save both payloads and responses to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        company_url: URL of the company website
        min_tickets_per_part: Minimum number of tickets per part
        max_tickets_per_part: Maximum number of tickets per part
        stages: Dictionary of stage names to IDs
        parts: Dictionary of parts information
        rev_orgs: List of rev org information
        openai_credentials: Dictionary containing OpenAI credentials
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        List of ticket details
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Tickets: {message}", percent)

    try:
        # Phase 1: GPT Content Generation (0-40%)
        total_expected = len(parts) * max_tickets_per_part
        update_progress(f"Preparing to generate content for approximately {total_expected} tickets...", 0)

        tickets = prompt_gpt_for_tickets(
            parts,
            company_url,
            min_tickets_per_part,
            max_tickets_per_part,
            openai_credentials,
            session_path,
            # Scale GPT progress to 0-40%
            progress_callback=lambda msg, pct: update_progress(
                msg.replace("Prompting ChatGPT: ", ""),
                pct * 0.4
            )
        )

        print("\n========================================")
        print("Creating Tickets in DevRev")
        print("========================================")

        # Phase 2: Ticket Creation (40-100%)
        total_tickets = len(tickets)
        update_progress(f"Creating tickets in DevRev (0/{total_tickets})...", 40)

        responses = []
        failed_tickets = []

        for idx, ticket in enumerate(tickets, 1):
            try:
                # Convert part name to part ID
                part_id = parts[ticket["applies_to_part"]]["id"]
                
                # Update ticket with required fields
                ticket_payload = {
                    **ticket,
                    "stage": {"id": stages[ticket["stage"]]},
                    "applies_to_part": part_id,
                    "owned_by": [parts[ticket["applies_to_part"]]["owned_by"]],
                    "rev_org": random.choice(rev_orgs)["id"]
                }

                response = post_objects(PAT, base_url=base_url, object_type="works", payloads=[ticket_payload])
                responses.extend(response)

                current_progress = 40 + ((idx/total_tickets) * 60)
                update_progress(f"Creating ticket in DevRev ({idx}/{total_tickets})", current_progress)
                logger.info(f"Created ticket: {ticket['title']}")

            except Exception as e:
                logger.error(f"Failed to create ticket: {ticket['title']} - Error: {str(e)}")
                failed_tickets.append({
                    "title": ticket['title'],
                    "error": str(e),
                    "payload": ticket
                })
                continue

        # Save failed tickets if any
        if failed_tickets:
            save_payload_to_file(failed_tickets, "tickets_failed", session_path)

        # Save successful responses
        if responses:
            save_payload_to_file(responses, "tickets_responses", session_path)

        # Extract and save ticket details
        ticket_details = [
            {
                "id": response["work"]["id"],
                "title": response["work"]["title"],
                "body": response["work"]["body"],
                "stage": response["work"]["stage"]["name"],
                "severity": response["work"]["severity"],
                "applies_to_part": response["work"]["applies_to_part"]["id"]
            } for response in responses
        ]

        # Save processed ticket details
        save_payload_to_file(ticket_details, "tickets_processed", session_path)

        update_progress(f"Successfully created {len(ticket_details)} tickets", 100)
        print("========================================")
        return ticket_details

    except Exception as e:
        error_message = f"Error creating tickets: {str(e)}"
        update_progress(error_message, 0)
        raise
def create_issues(PAT, base_url, company_url, min_issues_per_part, max_issues_per_part, quantity_of_tickets_linked_to_issues, stages, parts, dev_user_ids, openai_credentials, session_path=None, progress_callback=None):
    """
    Create issues and save both payloads and responses to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        company_url: URL of the company website
        min_issues_per_part: Minimum number of issues per part
        max_issues_per_part: Maximum number of issues per part
        quantity_of_tickets_linked_to_issues: Number of tickets to link to issues
        stages: Dictionary of stage names to IDs
        parts: Dictionary of parts information
        dev_user_ids: List of developer user IDs
        openai_credentials: Dictionary containing OpenAI credentials
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        List of issue IDs
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Issues: {message}", percent)

    try:
        # Phase 1: GPT Content Generation (0-40%)
        total_expected = len(parts) * max_issues_per_part
        update_progress(f"Preparing to generate content for approximately {total_expected} issues...", 0)

        issues = prompt_gpt_for_issues(
            parts,
            company_url,
            min_issues_per_part,
            max_issues_per_part,
            openai_credentials,
            session_path,
            # Scale GPT progress to 0-40%
            progress_callback=lambda msg, pct: update_progress(
                msg.replace("Prompting ChatGPT: ", ""),
                pct * 0.4
            )
        )

        print("\n========================================")
        print("Creating Issues in DevRev")
        print("========================================")

        # Phase 2: Issue Creation (40-100%)
        total_issues = len(issues)
        update_progress(f"Creating issues in DevRev (0/{total_issues})...", 40)

        responses = []
        failed_issues = []

        for idx, issue in enumerate(issues, 1):
            try:
                # Convert part name to part ID
                part_id = parts[issue["applies_to_part"]]["id"]
                
                # Update issue with required fields
                issue_payload = {
                    **issue,
                    "stage": {"id": stages[issue["stage"]]},
                    "applies_to_part": part_id,
                    "owned_by": [random.choice(dev_user_ids)],
                    "priority": issue.get("priority", "p2")  # Default to p2 if not set
                }

                response = post_objects(PAT, base_url=base_url, object_type="works", payloads=[issue_payload])
                responses.extend(response)

                current_progress = 40 + ((idx/total_issues) * 60)
                update_progress(f"Creating issue in DevRev ({idx}/{total_issues})", current_progress)
                logger.info(f"Created issue: {issue['title']}")

            except Exception as e:
                logger.error(f"Failed to create issue: {issue['title']} - Error: {str(e)}")
                failed_issues.append({
                    "title": issue['title'],
                    "error": str(e),
                    "payload": issue
                })
                continue

        # Save failed issues if any
        if failed_issues:
            save_payload_to_file(failed_issues, "issues_failed", session_path)

        # Save successful responses
        if responses:
            save_payload_to_file(responses, "issues_responses", session_path)

        # Extract issue IDs
        issue_ids = [response["work"]["id"] for response in responses]

        update_progress(f"Successfully created {len(issue_ids)} issues", 100)
        print("========================================")
        return issue_ids

    except Exception as e:
        error_message = f"Error creating issues: {str(e)}"
        update_progress(error_message, 0)
        raise

def create_opportunities(PAT, base_url, accounts, dev_user_ids, stages, session_path=None, progress_callback=None):
    """
    Create opportunities and save both payloads and responses to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        accounts: List of account information
        dev_user_ids: List of developer user IDs
        stages: Dictionary of stage names to IDs
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        List of created opportunity responses
    """
    def update_progress(message, percent):
        if progress_callback:
            progress_callback(f"Opportunities: {message}", percent)

    try:
        print("\n========================================")
        print("Creating Sales Opportunities")
        print("========================================")

        # Phase 1: Generate Opportunity Payloads (0-30%)
        update_progress("Preparing opportunity data...", 0)
        
        # Create and save initial payload
        opportunities = create_opportunities_payload(accounts, dev_user_ids, stages)
        save_payload_to_file(opportunities, "opportunities", session_path)
        
        total_opps = len(opportunities)
        base_opps = len([opp for opp in opportunities if "Upsell" not in opp.get('title', '')])
        upsell_opps = total_opps - base_opps
        
        update_progress(f"Prepared {base_opps} base opportunities and {upsell_opps} upsell opportunities", 30)

        # Phase 2: Opportunity Creation (30-100%)
        responses = []
        failed_opportunities = []

        for idx, opp in enumerate(opportunities, 1):
            try:
                response = post_objects(PAT, base_url=base_url, object_type="works", payloads=[opp])
                responses.extend(response)
                
                current_progress = 30 + ((idx/total_opps) * 70)
                update_progress(f"Creating opportunity ({idx}/{total_opps})", current_progress)
                logger.info(f"Created opportunity: {opp['title']}")

            except Exception as e:
                logger.error(f"Failed to create opportunity: {opp['title']} - Error: {str(e)}")
                failed_opportunities.append({
                    "title": opp['title'],
                    "error": str(e),
                    "payload": opp
                })
                continue

        # Save failed opportunities if any
        if failed_opportunities:
            save_payload_to_file(failed_opportunities, "opportunities_failed", session_path)

        # Save successful responses
        if responses:
            save_payload_to_file(responses, "opportunities_responses", session_path)

        update_progress(f"Successfully created {len(responses)} opportunities", 100)
        print("========================================")
        return responses

    except Exception as e:
        error_message = f"Error creating opportunities: {str(e)}"
        update_progress(error_message, 0)
        raise

def create_opportunities_payload(accounts, dev_user_ids, stages):
    """
    Create opportunities payload
    Args:
        accounts: List of account information
        dev_user_ids: List of developer user IDs
        stages: Dictionary of stage names to IDs
    Returns:
        List of opportunity payloads
    """
    opportunities = []
    stage_forecast_mapping = {
        "qualification": "pipeline",
        "stalled": "pipeline",
        "validation": "upside",
        "negotiation": "strong_upside",
        "contract": "commit",
        "closed_won": "won",
        "closed_lost": "omitted"
    }

    for account in accounts:
        stage = random.choice(random.sample(list(stage_forecast_mapping.keys()), 3))
        arr = random.randint(10000, 100000)
        opportunity = {
            "type": "opportunity",
            "title": account["name"],
            "annual_recurring_revenue": arr,
            "amount": round(arr * (random.randint(12, 36) / 12), 2),
            "forecast_category": stage_forecast_mapping[stage],
            "owned_by": [random.choice(dev_user_ids)],
            "account": account["id"],
            "stage": {"id": stages[stage]}
        }
        opportunities.append(opportunity)

    for opportunity in opportunities:
        if opportunity["stage"]["id"] == stages["closed_won"]:
            arr = random.randint(10000, 50000)
            stage = random.choice(["negotiation", "contract"])
            new_opportunity = {
                "type": "opportunity",
                "title": opportunity["title"] + " - Upsell",
                "annual_recurring_revenue": arr,
                "amount": round(arr * (random.randint(12, 36) / 12), 2),
                "forecast_category": stage_forecast_mapping[stage],
                "owned_by": opportunity["owned_by"],
                "account": opportunity["account"],
                "stage": {"id": stages[stage]}
            }
            opportunities.append(new_opportunity)

    return opportunities
def get_revusers(PAT, base_url):
    """
    Get all rev-users from DevRev
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
    Returns:
        List of rev-users
    """
    rev_users = load_objects(PAT, base_url, "rev-users")
    return rev_users

def get_devusers(PAT, base_url):
    """
    Get all dev-users from DevRev
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
    Returns:
        List of dev-user IDs
    """
    response = load_objects(PAT, base_url, "dev-users")
    dev_user_ids = [r['id'] for r in response]
    return dev_user_ids

def get_accounts(PAT, base_url):
    """
    Get all accounts and rev-orgs from DevRev
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
    Returns:
        Tuple of [accounts, rev_orgs]
    """
    response = load_objects(PAT, base_url, "rev-orgs")
    accounts = []
    rev_orgs = []

    for rev_org in response:
        if 'account' in rev_org:
            account = {
                'name': str(rev_org['account']['display_name']),
                'id': str(rev_org['account']['id']),
                'display_id': str(rev_org['account']['display_id'])
            }
            accounts.append(account)

            rev_org_entry = {
                'name': str(rev_org['display_name']),
                'id': str(rev_org['id']),
                'display_id': str(rev_org['display_id'])
            }
            rev_orgs.append(rev_org_entry)

    return accounts, rev_orgs

def get_parts(PAT, base_url):
    """
    Get all parts from DevRev
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
    Returns:
        Dictionary of parts information
    """
    parts = load_objects(PAT, base_url, "parts")
    result = {
        part["name"]: {
            "id": part["id"],
            "type": part["type"],
            "owned_by": part["owned_by"][0]["id"]
        } for part in parts
    }
    return result

def get_revoid(PAT, base_url):
    """
    Get RevOID from DevRev
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
    Returns:
        RevOID string
    """
    get_dev_org_self_url = base_url + "dev-orgs.self"
    headers = {
        'Authorization': f'Bearer {PAT}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(get_dev_org_self_url, headers=headers)
        response.raise_for_status()
        return response.json()["dev_org"]["display_id"].lstrip("DEV-")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error loading objects with exception: {e}")
        logger.error(response.json())
        raise

def start_web_scrape(url, depth, PAT, base_url):
    """
    Start web scraping for a given URL
    Args:
        url: URL to scrape
        depth: Crawling depth
        PAT: DevRev PAT
        base_url: Base URL for API
    Returns:
        Web crawler job ID or None if failed
    """
    if not url:
        return None

    payload = {
        "urls": [url],
        "applies_to_parts": ["PROD-1"],
        "max_depth": depth,
        "frequency": 0
    }

    post_web_scrape_url = base_url + "web-crawler-jobs.create"
    headers = {
        'Authorization': f'Bearer {PAT}',
        'Content-Type': 'application/json'
    }

    try:
        print(f"\n========================================")
        print(f"Starting web scrape for: {url}")
        print(f"Crawl depth: {depth}")
        print("========================================")
        
        response = requests.post(
            post_web_scrape_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        job_id = response.json()["web_crawler_job"]["id"]
        
        print(f"✅ Web scrape job started successfully")
        print(f"Job ID: {job_id}")
        print("========================================")
        
        logger.info(f"Web scrape started for {url} with job ID: {job_id}")
        return job_id

    except requests.exceptions.Timeout:
        print("❌ Web scrape request timed out")
        logger.error(f"Timeout while starting web scrape for {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error scraping url: {str(e)}")
        logger.error(f"Error starting web scrape for {url}: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(e.response.json())
        return None

def clean_org(PAT, base_url, session_path=None, progress_callback=None):
    """
    Clean up organization by deleting various objects and save cleanup status to session directory
    Args:
        PAT: DevRev PAT
        base_url: Base URL for API
        session_path: Path to session directory
        progress_callback: Callback function for progress updates
    Returns:
        Dictionary containing cleanup status
    """
    total_steps = 5
    current_step = 0
    cleanup_status = {
        "parts": {"total": 0, "deleted": 0, "failed": 0},
        "works": {"total": 0, "deleted": 0, "failed": 0},
        "rev_users": {"total": 0, "deleted": 0, "failed": 0},
        "accounts": {"total": 0, "deleted": 0, "failed": 0},
        "dev_users": {"total": 0, "deleted": 0, "failed": 0, "protected": 0}
    }

    try:
        # Step 1: Delete parts
        current_step += 1
        base_progress = ((current_step - 1) / total_steps) * 100
        print(f"\nStep {current_step}/{total_steps}: Processing parts...")
        if progress_callback:
            progress_callback("Loading parts...", base_progress)

        stock_parts = load_objects(PAT, base_url, "parts", session_path)
        stock_parts_ids = [part['id'] for part in stock_parts if part['type'] != 'product']
        cleanup_status["parts"]["total"] = len(stock_parts_ids)
        
        print(f"Found {len(stock_parts_ids)} stock parts.")
        if stock_parts_ids:
            failed_deletions = delete_objects(PAT, base_url, "parts", stock_parts_ids,
                progress_callback=progress_callback,
                base_progress=base_progress,
                step_weight=20)
            cleanup_status["parts"]["failed"] = len(failed_deletions)
            cleanup_status["parts"]["deleted"] = len(stock_parts_ids) - len(failed_deletions)
        else:
            print("No parts to delete.")
            if progress_callback:
                progress_callback("No parts to delete", base_progress + 20)

        # Save status after parts deletion
        if session_path:
            save_payload_to_file(cleanup_status, "cleanup_status_responses", session_path)

        # Step 2: Delete works
        current_step += 1
        base_progress = ((current_step - 1) / total_steps) * 100
        print(f"\nStep {current_step}/{total_steps}: Processing works...")
        if progress_callback:
            progress_callback("Loading works...", base_progress)

        stock_works = load_objects(PAT, base_url, "works", session_path)
        stock_works_ids = [work['id'] for work in stock_works]
        cleanup_status["works"]["total"] = len(stock_works_ids)
        
        print(f"Found {len(stock_works_ids)} stock works.")
        if stock_works_ids:
            failed_deletions = delete_objects(PAT, base_url, "works", stock_works_ids,
                progress_callback=progress_callback,
                base_progress=base_progress,
                step_weight=20)
            cleanup_status["works"]["failed"] = len(failed_deletions)
            cleanup_status["works"]["deleted"] = len(stock_works_ids) - len(failed_deletions)
        else:
            print("No works to delete.")
            if progress_callback:
                progress_callback("No works to delete", base_progress + 20)

        # Save status after works deletion
        if session_path:
            save_payload_to_file(cleanup_status, "cleanup_status_responses", session_path)

        # Step 3: Delete rev_users
        current_step += 1
        base_progress = ((current_step - 1) / total_steps) * 100
        print(f"\nStep {current_step}/{total_steps}: Processing rev-users...")
        if progress_callback:
            progress_callback("Loading rev-users...", base_progress)

        rev_users = load_objects(PAT, base_url, "rev-users", session_path)
        rev_user_ids = [user['id'] for user in rev_users]
        cleanup_status["rev_users"]["total"] = len(rev_user_ids)
        
        print(f"Found {len(rev_user_ids)} rev users.")
        if rev_user_ids:
            failed_deletions = delete_objects(PAT, base_url, "rev-users", rev_user_ids,
                progress_callback=progress_callback,
                base_progress=base_progress,
                step_weight=20)
            cleanup_status["rev_users"]["failed"] = len(failed_deletions)
            cleanup_status["rev_users"]["deleted"] = len(rev_user_ids) - len(failed_deletions)
        else:
            print("No rev users to delete.")
            if progress_callback:
                progress_callback("No rev-users to delete", base_progress + 20)

        # Save status after rev_users deletion
        if session_path:
            save_payload_to_file(cleanup_status, "cleanup_status_responses", session_path)

        # Step 4: Delete accounts
        current_step += 1
        base_progress = ((current_step - 1) / total_steps) * 100
        print(f"\nStep {current_step}/{total_steps}: Processing accounts...")
        if progress_callback:
            progress_callback("Loading accounts...", base_progress)

        accounts = load_objects(PAT, base_url, "accounts", session_path)
        account_ids = [account['id'] for account in accounts]
        cleanup_status["accounts"]["total"] = len(account_ids)
        
        print(f"Found {len(account_ids)} accounts.")
        if account_ids:
            failed_deletions = delete_objects(PAT, base_url, "accounts", account_ids,
                progress_callback=progress_callback,
                base_progress=base_progress,
                step_weight=20)
            cleanup_status["accounts"]["failed"] = len(failed_deletions)
            cleanup_status["accounts"]["deleted"] = len(account_ids) - len(failed_deletions)
        else:
            print("No accounts to delete.")
            if progress_callback:
                progress_callback("No accounts to delete", base_progress + 20)

        # Save status after accounts deletion
        if session_path:
            save_payload_to_file(cleanup_status, "cleanup_status_responses", session_path)

        # Step 5: Delete dev_users
        current_step += 1
        base_progress = ((current_step - 1) / total_steps) * 100
        print(f"\nStep {current_step}/{total_steps}: Processing dev-users...")
        if progress_callback:
            progress_callback("Loading dev-users...", base_progress)

        dev_users = load_objects(PAT, base_url, "dev-users", session_path)
        dev_user_ids = [user['id'] for user in dev_users if not user['id'].endswith('devu/1')]
        cleanup_status["dev_users"]["total"] = len(dev_users)
        cleanup_status["dev_users"]["protected"] = len(dev_users) - len(dev_user_ids)
        
        print(f"Found {len(dev_users)} dev users ({len(dev_users) - len(dev_user_ids)} protected, {len(dev_user_ids)} deletable).")
        if dev_user_ids:
            failed_deletions = delete_objects(PAT, base_url, "dev-users", dev_user_ids,
                progress_callback=progress_callback,
                base_progress=base_progress,
                step_weight=20)
            cleanup_status["dev_users"]["failed"] = len(failed_deletions)
            cleanup_status["dev_users"]["deleted"] = len(dev_user_ids) - len(failed_deletions)
        else:
            print("No dev users to delete (only protected users remain).")
            if progress_callback:
                progress_callback("No dev-users to delete", base_progress + 20)

        # Save final cleanup status to session directory
        if session_path:
            save_payload_to_file(cleanup_status, "cleanup_status_responses", session_path)
            logger.info("Final cleanup status saved to session directory")

        if progress_callback:
            progress_callback("Cleanup process completed", 100)
        
        return cleanup_status

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        # Try to save error status
        if session_path:
            cleanup_status["error"] = str(e)
            save_payload_to_file(cleanup_status, "cleanup_status_responses", session_path)
        raise
