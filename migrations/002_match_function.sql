CREATE OR REPLACE FUNCTION match_visual_indices(
    query_embedding vector(1536),
    p_project_id VARCHAR,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 3
)
RETURNS TABLE (id UUID, image_url TEXT, detailed_description TEXT, similarity FLOAT)
LANGUAGE sql STABLE AS $$
    SELECT id, image_url, detailed_description,
           1 - (embedding_vector <=> query_embedding) AS similarity
    FROM project_visual_indices
    WHERE project_id = p_project_id
      AND 1 - (embedding_vector <=> query_embedding) > match_threshold
    ORDER BY embedding_vector <=> query_embedding
    LIMIT match_count;
$$;
