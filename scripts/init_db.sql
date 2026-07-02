-- Life Graph Database Initialization
-- This runs on first container start

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for gen_random_uuid (built-in to PG 13+ but explicit is fine)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
