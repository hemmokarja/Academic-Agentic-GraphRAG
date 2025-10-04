// Numeric and analytical property indexes
CREATE INDEX eval_metric_value IF NOT EXISTS FOR (n:EvaluationResult) ON (n.metricValue);
CREATE INDEX method_year IF NOT EXISTS FOR (n:Method) ON (n.introducedYear);
CREATE INDEX dataset_num_papers IF NOT EXISTS FOR (n:Dataset) ON (n.numberPapers);
CREATE INDEX method_num_papers IF NOT EXISTS FOR (n:Method) ON (n.numberPapers);
