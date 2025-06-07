-- First, add the backend node to the cluster
ALTER SYSTEM ADD BACKEND "172.20.80.3:9050";

-- Check if backends are registered
SHOW PROC '/backends';

-- Optionally check cluster health
SHOW PROC '/health';

-- Adjust replica allocation if needed
-- ADMIN SET FRONTEND CONFIG ("max_replication_num" = "1", "min_replication_num" = "1");
