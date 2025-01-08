document.addEventListener('alpine:init', () => {
    Alpine.data('demoOrgGenerator', () => ({
        // Form Data
        formData: {
            devorgPat: '',
            websiteUrl: '',
            knowledgebaseUrl: '',
            numArticles: 4,
            numIssues: 4
        },

        // UI State
        advancedSettings: false,
        isLoading: false,
        progress: 0,
        statusMessage: '',
        showSuccess: false,
        errors: {},
        sessionId: null,  // Added for download functionality

        // Default settings - clean_org disabled by default, others enabled
        settings: {
            clean_org: false,
            deactivate_auto_reply: true,
            set_SLA: true
        },

        // Methods
        async handleGenerate() {
            if (!this.validateForm()) {
                return;
            }
            this.isLoading = true;
            this.showSuccess = false;
            this.progress = 0;

            try {
                // If clean_org is enabled, run cleanup first
                if (this.settings.clean_org) {
                    this.statusMessage = 'Starting cleanup phase...';
                    const cleanupResponse = await fetch('/api/cleanup', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            devorgPat: this.formData.devorgPat
                        })
                    });

                    if (!cleanupResponse.ok) {
                        throw new Error('Cleanup phase failed');
                    }

                    const cleanupData = await cleanupResponse.json();
                    this.sessionId = cleanupData.sessionId;  // Store the session ID

                    // Wait for cleanup to complete before proceeding
                    await new Promise((resolve, reject) => {
                        const checkCleanup = setInterval(async () => {
                            try {
                                const progressResponse = await fetch(`/api/progress/${cleanupData.sessionId}`);
                                const progressData = await progressResponse.json();

                                // Update UI with cleanup progress
                                this.progress = progressData.progress;
                                this.statusMessage = `Cleanup phase: ${progressData.status}`;

                                if (progressData.error) {
                                    clearInterval(checkCleanup);
                                    reject(new Error(progressData.error));
                                }

                                if (progressData.complete) {
                                    clearInterval(checkCleanup);
                                    resolve();
                                }
                            } catch (error) {
                                clearInterval(checkCleanup);
                                reject(new Error('Lost connection during cleanup'));
                            }
                        }, 1000);
                    });

                    // Reset progress before starting content generation
                    this.progress = 0;
                }

                // Proceed with content generation
                this.statusMessage = 'Starting content generation...';
                console.log('Starting generation with configuration settings:', {
                    clean_org: this.settings.clean_org,
                    deactivate_auto_reply: this.settings.deactivate_auto_reply,
                    set_SLA: this.settings.set_SLA
                });

                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        ...this.formData,
                        settings: this.settings
                    })
                });

                if (!response.ok) {
                    throw new Error('Generation failed');
                }

                const data = await response.json();
                this.sessionId = data.sessionId;  // Store the session ID
                this.pollProgress(data.sessionId);

            } catch (error) {
                this.handleError(`Process failed: ${error.message}`);
            }
        },

        handleCleanOrgToggle(event) {
            if (event.target.checked) {
                // Prevent the immediate toggle
                event.preventDefault();
                // Show warning dialog
                if (confirm("⚠️ Warning!\n\nThis will clean out all accounts, trails, tickets, issues and opportunities before the org gets created.")) {
                    this.settings.clean_org = true;
                }
            } else {
                this.settings.clean_org = false;
            }
        },

        async handleCleanup() {
            // Check if PAT is provided
            if (!this.formData.devorgPat) {
                this.errors.devorgPat = 'DevOrg PAT is required for cleanup';
                return;
            }

            this.isLoading = true;
            this.showSuccess = false;
            this.progress = 0;
            this.statusMessage = 'Starting cleanup...';

            try {
                console.log('Starting cleanup process...'); // Debug log
                const response = await fetch('/api/cleanup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        devorgPat: this.formData.devorgPat
                    })
                });

                console.log('Cleanup API response:', response.status); // Debug log

                if (!response.ok) {
                    throw new Error(`Cleanup failed with status: ${response.status}`);
                }

                const data = await response.json();
                console.log('Cleanup session ID:', data.sessionId); // Debug log
                this.sessionId = data.sessionId;  // Store the session ID

                if (data.sessionId) {
                    this.pollProgress(data.sessionId);
                } else {
                    throw new Error('No session ID received from server');
                }

            } catch (error) {
                console.error('Cleanup error:', error); // Debug log
                this.handleError(`Failed to start cleanup process: ${error.message}`);
                this.isLoading = false;
            }
        },

        async pollProgress(sessionId) {
            const pollInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/progress/${sessionId}`);
                    const data = await response.json();

                    this.progress = data.progress;
                    this.statusMessage = data.status;

                    if (data.complete || data.error) {
                        clearInterval(pollInterval);
                        this.isLoading = false;
                        if (data.error) {
                            this.handleError(data.error);
                        } else {
                            this.showSuccess = true;
                        }
                    }
                } catch (error) {
                    clearInterval(pollInterval);
                    this.handleError('Lost connection to server');
                    this.isLoading = false;
                }
            }, 1000);
        },

        validateForm() {
            this.errors = {};

            if (!this.formData.devorgPat) {
                this.errors.devorgPat = 'DevOrg PAT is required';
            }

            if (!this.formData.websiteUrl) {
                this.errors.websiteUrl = 'Website URL is required';
            } else if (!this.isValidUrl(this.formData.websiteUrl)) {
                this.errors.websiteUrl = 'Please enter a valid URL';
            }

            if (this.formData.knowledgebaseUrl && !this.isValidUrl(this.formData.knowledgebaseUrl)) {
                this.errors.knowledgebaseUrl = 'Please enter a valid URL';
            }

            // Validate minimum values for tickets and issues
            if (this.formData.numArticles < 2) {
                this.errors.numArticles = 'Minimum number of tickets per part is 2';
            }

            if (this.formData.numIssues < 2) {
                this.errors.numIssues = 'Minimum number of issues per part is 2';
            }

            return Object.keys(this.errors).length === 0;
        },

        isValidUrl(string) {
            try {
                new URL(string);
                return true;
            } catch (_) {
                return false;
            }
        },

        handleError(message) {
            this.isLoading = false;
            this.statusMessage = `Error: ${message}`;
            console.error(message);
        },

        // Add download method
        async downloadLogs() {
            if (!this.sessionId) return;
            
            try {
                window.location.href = `/api/download/${this.sessionId}`;
            } catch (error) {
                this.handleError(`Download failed: ${error.message}`);
            }
        }
    }))
});