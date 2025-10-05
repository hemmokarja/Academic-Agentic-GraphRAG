// Paper
CREATE INDEX paper_title IF NOT EXISTS FOR (n:Paper) ON (n.title);
CREATE INDEX paper_arxiv IF NOT EXISTS FOR (n:Paper) ON (n.hasArXivId);
CREATE INDEX paper_date IF NOT EXISTS FOR (n:Paper) ON (n.date);
CREATE INDEX paper_creator IF NOT EXISTS FOR (n:Paper) ON (n.creator);

// Dataset
CREATE INDEX dataset_name IF NOT EXISTS FOR (n:Dataset) ON (n.fullname);
CREATE INDEX dataset_title IF NOT EXISTS FOR (n:Dataset) ON (n.title);
CREATE INDEX dataset_issued IF NOT EXISTS FOR (n:Dataset) ON (n.issued);

// Method
CREATE INDEX method_name IF NOT EXISTS FOR (n:Method) ON (n.name);

// Task
CREATE INDEX task_name IF NOT EXISTS FOR (n:Task) ON (n.name);

// Category / Area
CREATE INDEX category_name IF NOT EXISTS FOR (n:Category) ON (n.name);
CREATE INDEX area_name IF NOT EXISTS FOR (n:Area) ON (n.name);

// Repository
CREATE INDEX repo_framework IF NOT EXISTS FOR (n:Repository) ON (n.hasFramework);

// Conference
CREATE INDEX conf_name IF NOT EXISTS FOR (n:Conference) ON (n.name);
CREATE INDEX conf_acronym IF NOT EXISTS FOR (n:Conference) ON (n.acronym);

// Author
CREATE INDEX author_name IF NOT EXISTS FOR (n:Author) ON (n.name);
