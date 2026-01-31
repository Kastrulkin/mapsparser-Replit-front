"""
Feature flags for Phase 3.5 Repository Pattern migration
"""
import os

# Repository Pattern Feature Flags (per-domain granularity)
USE_BUSINESS_REPOSITORY = os.getenv('USE_BUSINESS_REPOSITORY', 'false').lower() == 'true'
USE_SERVICE_REPOSITORY = os.getenv('USE_SERVICE_REPOSITORY', 'false').lower() == 'true'
USE_REVIEW_REPOSITORY = os.getenv('USE_REVIEW_REPOSITORY', 'false').lower() == 'true'

# Database type
DB_TYPE = os.getenv('DB_TYPE', 'sqlite').lower()
