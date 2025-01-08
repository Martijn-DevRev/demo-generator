"""
Configuration features for DevRev org setup
Contains all configuration-related functions that can be enabled/disabled
"""
import requests
import logging

# Set up logging
logger = logging.getLogger(__name__)

class ConfigurationFeatures:
    def __init__(self, PAT, base_url):
        self.PAT = PAT
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {PAT}',
            'Content-Type': 'application/json'
        }

    def deactivate_auto_reply_snapin(self, progress_callback=None):
        """Deactivates the auto reply snap-in"""
        try:
            print("\n========================================")
            print("Starting auto-reply snap-in deactivation")
            print("========================================")
            logger.info("Starting auto-reply snap-in deactivation process")
            if progress_callback:
                progress_callback("Starting auto-reply snap-in deactivation...", 0)

            # Get auto reply Snap-In ID
            get_dev_org_self_url = self.base_url + "snap-ins.list"
            logger.info("Fetching snap-ins list...")
            response = requests.get(get_dev_org_self_url, headers=self.headers)
            response.raise_for_status()

            auto_reply_snap_in = None
            for snap_in in response.json()["snap_ins"]:
                if 'automations' in snap_in and snap_in['automations'] and snap_in['automations'][0]['name'] == "auto_reply":
                    auto_reply_snap_in = snap_in
                    logger.info(f"Found auto-reply snap-in with ID: {snap_in['id']}")
                    break

            if progress_callback:
                progress_callback("Found auto-reply snap-in, checking status...", 50)

            if auto_reply_snap_in:
                # Get the current state of the snap-in
                current_state = auto_reply_snap_in.get('state', '').lower()
                is_active = auto_reply_snap_in.get('is_active', False)
                
                logger.info(f"Current snap-in state: {current_state}, is_active: {is_active}")

                # If already inactive or disabled, no need to deactivate
                if not is_active or current_state == 'disabled':
                    logger.info("Auto-reply snap-in is already inactive")
                    if progress_callback:
                        progress_callback("Auto-reply snap-in is already inactive", 100)
                    print("========================================")
                    return True

                # Deactivate auto reply Snap-In
                deactivate_snapin_url = self.base_url + "snap-ins.deactivate"
                payload = {
                    "force": False,
                    "id": auto_reply_snap_in["display_id"]
                }
                
                logger.info(f"Attempting to deactivate snap-in with display_id: {auto_reply_snap_in['display_id']}")
                logger.debug("Sending deactivate request with payload: %s", payload)
                
                try:
                    response = requests.post(deactivate_snapin_url, headers=self.headers, json=payload)
                    response_content = response.json() if response.content else {}
                    logger.debug(f"Deactivate response: {response_content}")
                    
                    if response.status_code == 400 and "cannot be deactivated from inactive state" in response.text:
                        logger.info("Snap-in is already inactive")
                        if progress_callback:
                            progress_callback("Auto-reply snap-in is already inactive", 100)
                        return True
                    
                    response.raise_for_status()
                    logger.info("Successfully deactivated auto-reply snap-in")
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request failed: {str(e)}")
                    logger.error(f"Response content: {response.text}")
                    raise

                if progress_callback:
                    progress_callback("Auto-reply snap-in deactivated successfully", 100)
                print("========================================")
                return True
            else:
                logger.info("No auto-reply snap-in found")
                if progress_callback:
                    progress_callback("No auto-reply snap-in found to deactivate", 100)
                print("========================================")
                return False

        except requests.exceptions.RequestException as e:
            error_msg = f"Error managing auto-reply snap-in: {str(e)}"
            logger.error(error_msg)
            print("========================================")
            if progress_callback:
                progress_callback(f"Error: {error_msg}", 0)
            raise

    def set_default_sla(self, revoid, progress_callback=None):
        """Sets up the default SLA configuration"""
        try:
            print("\n========================================")
            print("Starting SLA configuration setup")
            print("========================================")
            logger.info(f"Starting SLA configuration setup for RevOID: {revoid}")
            if progress_callback:
                progress_callback("Starting SLA configuration...", 0)

            create_default_sla_url = self.base_url + "slas.create"
            logger.info(f"Setting up SLA for RevOID: {revoid}")

            sla_payload = {
                "applies_to": ["conversation", "ticket"],
                "name": "Default",
                "sla_type": "external",
                "policies": [
                    {
                        "metrics": [{
                            "metric": f"don:core:dvrv-us-1:devo/{revoid}:metric_definition/3",
                            "performance": 0,
                            "target": 25920,
                            "warning_target": 12960
                        }],
                        "name": "New ticket policy",
                        "selector": {
                            "applies_to": "ticket",
                            "custom_fields": {},
                            "severity": ["low"]
                        }
                    },
                    {
                        "metrics": [{
                            "metric": f"don:core:dvrv-us-1:devo/{revoid}:metric_definition/3",
                            "performance": 0,
                            "target": 11880,
                            "warning_target": 5940
                        }],
                        "name": "New ticket policy",
                        "selector": {
                            "applies_to": "ticket",
                            "custom_fields": {},
                            "severity": ["medium"],
                            "tag_operation": "any"
                        }
                    },
                    {
                        "metrics": [{
                            "metric": f"don:core:dvrv-us-1:devo/{revoid}:metric_definition/3",
                            "performance": 0,
                            "target": 5400,
                            "warning_target": 2700
                        }],
                        "name": "New ticket policy",
                        "selector": {
                            "applies_to": "ticket",
                            "custom_fields": {},
                            "severity": ["high"],
                            "tag_operation": "any"
                        }
                    },
                    {
                        "metrics": [{
                            "metric": f"don:core:dvrv-us-1:devo/{revoid}:metric_definition/3",
                            "performance": 0,
                            "target": 2700,
                            "warning_target": 1380
                        }],
                        "name": "New ticket policy",
                        "selector": {
                            "applies_to": "ticket",
                            "custom_fields": {},
                            "severity": ["blocker"],
                            "tag_operation": "any"
                        }
                    },
                    {
                        "metrics": [
                            {
                                "metric": f"don:core:dvrv-us-1:devo/{revoid}:metric_definition/1",
                                "performance": 0,
                                "target": 30,
                                "warning_target": 20
                            },
                            {
                                "metric": f"don:core:dvrv-us-1:devo/{revoid}:metric_definition/2",
                                "performance": 0,
                                "target": 10,
                                "warning_target": 5
                            }
                        ],
                        "name": "New conversation policy",
                        "selector": {
                            "applies_to": "conversation",
                            "custom_fields": {},
                            "tag_operation": "any"
                        }
                    }
                ]
            }

            if progress_callback:
                progress_callback("Creating SLA configuration...", 50)

            logger.debug("Sending SLA creation request with payload: %s", sla_payload)
            response = requests.post(create_default_sla_url, headers=self.headers, json=sla_payload)
            response.raise_for_status()
            
            logger.info("Created default SLA as draft")
            sla_id = response.json()["sla"]["id"]
            logger.info(f"SLA created with ID: {sla_id}")

            if progress_callback:
                progress_callback("Publishing SLA configuration...", 75)

            if sla_id:
                transition_sla_url = self.base_url + "slas.transition"
                publish_payload = {
                    "id": sla_id,
                    "status": "published"
                }
                
                logger.debug("Publishing SLA with payload: %s", publish_payload)
                response = requests.post(transition_sla_url, headers=self.headers, json=publish_payload)
                response.raise_for_status()
                
                logger.info("SLA transitioned to published")
                if progress_callback:
                    progress_callback("SLA configuration completed successfully", 100)
                print("========================================")
                return True
            
            return False

        except requests.exceptions.RequestException as e:
            error_msg = f"Error configuring SLA: {str(e)}"
            logger.error(error_msg)
            print("========================================")
            if progress_callback:
                progress_callback(f"Error: {error_msg}", 0)
            raise
