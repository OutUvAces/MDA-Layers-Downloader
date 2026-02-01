def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Synchronous version of navigation warnings processing"""
    # For now, create a simple placeholder KML
    try:
        with open(task.output_path, 'w', encoding='utf-8') as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Navigation Warnings</name>
    <Placemark>
      <name>Navigation Warnings Data</name>
      <Point>
        <coordinates>0,0,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>""")
        report_progress(task.weight, f"✓ Created placeholder {task.name} KML")
        return True
    except Exception as e:
        report_progress(0, f"→ Error creating navigation warnings KML: {e}")
        return False

async def process_async(session, task, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of navigation warnings processing"""
    # For now, same as sync version
    return process(task, report_progress, output_dir, cache_dir)