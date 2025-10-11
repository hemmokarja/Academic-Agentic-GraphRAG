// Full-text search for human-readable text fields
CREATE FULLTEXT INDEX paper_search 
FOR (n:Paper) ON EACH [n.title, n.abstract];

CREATE FULLTEXT INDEX method_search 
FOR (n:Method) ON EACH [n.name, n.description, n.fullname];

CREATE FULLTEXT INDEX dataset_search 
FOR (n:Dataset) ON EACH [n.title, n.description];

CREATE FULLTEXT INDEX task_search 
FOR (n:Task) ON EACH [n.name, n.description];

CREATE FULLTEXT INDEX author_search 
FOR (n:Author) ON EACH [n.name];

CREATE FULLTEXT INDEX model_search 
FOR (n:Model) ON EACH [n.name];
