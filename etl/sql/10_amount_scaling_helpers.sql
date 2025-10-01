CREATE OR REPLACE FUNCTION core.scale_from_raw(raw NUMERIC, decimals INTEGER)
RETURNS NUMERIC
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
           WHEN raw IS NULL OR decimals IS NULL THEN NULL
           ELSE raw / power(10::NUMERIC, decimals)
         END;
$$;
