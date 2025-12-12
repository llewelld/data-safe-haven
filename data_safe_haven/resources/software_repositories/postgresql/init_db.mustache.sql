-- Initialization Script. Based on https://help.sonatype.com/en/install-nexus-repository-with-postgresql.html

-- Create a schema
CREATE SCHEMA nexus;

-- Create new user
CREATE USER nexus WITH PASSWORD '{{nexus_password}}';

-- Grant permissions for new user on the new database
GRANT ALL PRIVILEGES ON DATABASE nexus TO nexus;
GRANT ALL PRIVILEGES ON DATABASE nexus TO nexus;

-- Create extensions
CREATE EXTENSION pg_trgm SCHEMA nexus;
ALTER EXTENSION pg_trgm OWNER TO nexus;