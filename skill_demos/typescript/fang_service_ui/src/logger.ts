/**
 * fang_service_ui/src/logger.ts
 *
 * We replicate a simple JSON-based logger for consistency with the fang_service.
 * The Datadog APM code is commented out.
 */

// import tracer from 'dd-trace'; // <-- Datadog APM (commented)
// tracer.init(); // <-- Normally you would initialize Datadog here

// A simple function that logs messages in JSON format
export function logJSON(level: string, message: string, meta?: Record<string, any>) {
    const logEntry = {
      time: new Date().toISOString(),
      level,
      message,
      ...meta,
      // trace_id: placeholder or actual if integrated with Datadog
    };
    // Output to console in JSON
    console.log(JSON.stringify(logEntry));
  }
  