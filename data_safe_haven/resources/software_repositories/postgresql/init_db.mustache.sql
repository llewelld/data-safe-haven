-- Initialization Script. Based on https://help.sonatype.com/en/install-nexus-repository-with-postgresql.html

CREATE DATABASE nexus OWNER nexus ENCODING 'UTF8' LC_COLLATE = 'en_US.UTF-8' LC_CTYPE = 'en_US.UTF-8' TEMPLATE template0;