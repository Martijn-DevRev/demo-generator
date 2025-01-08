# Author: Martijn Bosschaart (based on the work by Jae Hosking)
import argparse
from devrev_objects import (
    clean_org, get_revoid,
    create_devusers, get_devusers, create_accounts,
    create_revusers, create_trails, create_tickets,
    create_issues, create_opportunities, load_objects,
    start_web_scrape
)
from configuration_features import ConfigurationFeatures
from dotenv import load_dotenv
import os
import logging

# Set up logging
logger = logging.getLogger(__name__)

def main(args, session_path=None, progress_callback=None):
    """
    Main function with progress reporting
    Args:
        args: Command line arguments
        session_path: Path to session directory
        progress_callback: function(status_message: str, progress_percentage: int)
    """
    def update_progress(status, progress):
        if progress_callback:
            progress_callback(status, progress)

    # Load environment variables
    load_dotenv(os.path.join('config', '.env'))

    # Initialize progress
    current_progress = 0
    total_steps = 11  # Total number of major steps in the process
    step_weight = 100 / total_steps
    update_progress("Initializing...", current_progress)

    # Set parameters
    PAT = args.pat
    company_url = args.company_url
    support_url = args.support_url
    min_tickets_per_part = 2
    max_tickets_per_part = args.max_tickets
    min_issues_per_part = 2
    max_issues_per_part = args.max_issues
    quantity_of_tickets_linked_to_issues = 30
    base_url = "https://api.devrev.ai/internal/"

    try:
        # Initialize configuration features
        config = ConfigurationFeatures(PAT, base_url)

        # Handle configuration settings if enabled
        if hasattr(args, 'settings'):
            logger.info("Configuration settings received: %s", args.settings)

            # Deactivate auto-reply snap-in if enabled
            if args.settings.get('deactivate_auto_reply', True):
                logger.info("Starting auto-reply snap-in deactivation process")
                current_progress += step_weight
                update_progress("Deactivating auto-reply snap-in...", current_progress)
                result = config.deactivate_auto_reply_snapin(
                    progress_callback=lambda status, prog: update_progress(
                        status,
                        current_progress - step_weight + (prog * step_weight / 100)
                    )
                )
                logger.info("Auto-reply snap-in deactivation completed: %s", "Success" if result else "No action needed")

            # Set up SLA if enabled
            if args.settings.get('set_SLA', True):
                logger.info("Starting SLA configuration process")
                current_progress += step_weight
                update_progress("Setting up SLA configuration...", current_progress)
                revoid = get_revoid(PAT, base_url)
                logger.info("Retrieved RevOID: %s", revoid)
                result = config.set_default_sla(
                    revoid,
                    progress_callback=lambda status, prog: update_progress(
                        status,
                        current_progress - step_weight + (prog * step_weight / 100)
                    )
                )
                logger.info("SLA configuration completed: %s", "Success" if result else "Failed")
        else:
            logger.warning("No settings object found in args - using defaults")

        # Start web scrape if enabled
        if hasattr(args, 'settings') and args.settings.get('crawl_site', True):
            current_progress += step_weight
            update_progress("Starting web scrapes...", current_progress)
            
            # First scrape the main company URL
            logger.info(f"Starting web scrape for company URL: {company_url}")
            company_job = start_web_scrape(company_url, 2, PAT, base_url)
            
            # If knowledge base URL is provided, scrape that too
            if support_url:
                logger.info(f"Starting web scrape for knowledge base URL: {support_url}")
                kb_job = start_web_scrape(support_url, 4, PAT, base_url)
                if kb_job:
                    logger.info("Both web scrapes initiated successfully")
            else:
                logger.info("No knowledge base URL provided, skipping second web scrape")

        # Create dev users
        current_progress += step_weight
        update_progress("Creating developer users...", current_progress)
        dev_user_ids = create_devusers(
            PAT,
            base_url=base_url,
            session_path=session_path,  # Make sure this is being passed
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Create accounts
        current_progress += step_weight
        update_progress("Creating accounts...", current_progress)
        accounts, rev_orgs = create_accounts(
            PAT,
            base_url=base_url,
            dev_users=dev_user_ids,
            session_path=session_path,
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Create rev users
        current_progress += step_weight
        update_progress("Creating customer users...", current_progress)
        rev_user_ids = create_revusers(
            PAT,
            base_url=base_url,
            rev_orgs=rev_orgs,
            session_path=session_path,
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Create trails (product hierarchy)
        current_progress += step_weight
        update_progress("Creating product hierarchy...", current_progress)
        parts = create_trails(
            PAT,
            company_url,
            dev_user_ids,
            base_url=base_url,
            openai_credentials={
                "organization": os.getenv('OPENAI_ORGANIZATION'),
                "project": os.getenv('OPENAI_PROJECT'),
                "api_key": os.getenv('OPENAI_API_KEY')
            },
            session_path=session_path,  # Add session_path here
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Load stages for tickets and issues
        current_progress += step_weight
        update_progress("Loading stages...", current_progress)
        try:
            stages = {
                stage["name"]: stage["id"]
                for stage in load_objects(PAT, base_url=base_url, object_type="stages.custom")
            }
        except Exception as e:
            update_progress(f"Error loading stages: {str(e)}", current_progress)
            raise

        # Create tickets
        current_progress += step_weight
        update_progress("Creating tickets...", current_progress)
        ticket_details = create_tickets(
            PAT,
            base_url=base_url,
            company_url=company_url,
            min_tickets_per_part=min_tickets_per_part,
            max_tickets_per_part=max_tickets_per_part,
            stages=stages,
            parts=parts,
            rev_orgs=rev_orgs,
            openai_credentials={
                "organization": os.getenv('OPENAI_ORGANIZATION'),
                "project": os.getenv('OPENAI_PROJECT'),
                "api_key": os.getenv('OPENAI_API_KEY')
            },
            session_path=session_path,  # Add session_path here
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Create issues
        current_progress += step_weight
        update_progress("Creating issues...", current_progress)
        issue_ids = create_issues(
            PAT,
            base_url=base_url,
            company_url=company_url,
            min_issues_per_part=min_issues_per_part,
            max_issues_per_part=max_issues_per_part,
            quantity_of_tickets_linked_to_issues=quantity_of_tickets_linked_to_issues,
            stages=stages,
            parts=parts,
            dev_user_ids=dev_user_ids,
            openai_credentials={
                "organization": os.getenv('OPENAI_ORGANIZATION'),
                "project": os.getenv('OPENAI_PROJECT'),
                "api_key": os.getenv('OPENAI_API_KEY')
            },
            session_path=session_path,  # Add session_path here
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Create opportunities
        current_progress += step_weight
        update_progress("Creating opportunities...", current_progress)
        create_opportunities(
            PAT,
            base_url=base_url,
            accounts=accounts,
            dev_user_ids=dev_user_ids,
            stages=stages,
            session_path=session_path,  # Add session_path here
            progress_callback=lambda status, prog: update_progress(
                status,
                current_progress - step_weight + (prog * step_weight / 100)
            )
        )

        # Final update
        update_progress("All operations completed successfully", 100)
    except Exception as e:
        update_progress(f"Error: {str(e)}", current_progress)
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create demo organization content')
    parser.add_argument('--pat', required=True, help='DevRev PAT')
    parser.add_argument('--company_url', required=True, help='Company URL')
    parser.add_argument('--support_url', required=True, help='Support URL')
    parser.add_argument('--max_tickets', type=int, default=5, help='Maximum number of tickets per part')
    parser.add_argument('--max_issues', type=int, default=5, help='Maximum number of issues per part')
    args = parser.parse_args()
    main(args)