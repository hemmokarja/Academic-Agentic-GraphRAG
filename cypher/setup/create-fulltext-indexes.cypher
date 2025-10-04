// Full-text search for human-readable text fields
CREATE FULLTEXT INDEX paper_search 
FOR (n:Paper) ON EACH [n.title, n.abstract, n.creatorName];

CREATE FULLTEXT INDEX method_search 
FOR (n:Method) ON EACH [n.name, n.description, n.fullname];

CREATE FULLTEXT INDEX dataset_search 
FOR (n:Dataset) ON EACH [n.title, n.description, n.fullname];

CREATE FULLTEXT INDEX task_search 
FOR (n:Task) ON EACH [n.name, n.description];
