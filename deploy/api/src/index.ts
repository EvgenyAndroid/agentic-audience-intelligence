// Cloudflare Worker in front of the upload API container (ADR 0005, stage B).
// Every request goes to a single container instance, because uploads are kept on that instance's disk.
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  API: DurableObjectNamespace<ApiContainer>;
  AIP_API_KEYS: string;
  AIP_ALLOWED_ORIGINS: string;
  AIP_RETENTION_HOURS: string;
}

export class ApiContainer extends Container<Env> {
  defaultPort = 8080;
  // Idle containers stop, and their disk goes with them: uploads never outlive 30 idle minutes or the
  // retention limit, whichever comes first.
  sleepAfter = "30m";
  // The API makes no outbound calls; with internet access off, uploaded data has no way out of the container.
  enableInternet = false;

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    this.envVars = {
      AIP_API_KEYS: env.AIP_API_KEYS ?? "{}",
      AIP_ALLOWED_ORIGINS: env.AIP_ALLOWED_ORIGINS,
      AIP_RETENTION_HOURS: env.AIP_RETENTION_HOURS,
    };
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return getContainer(env.API, "uploads").fetch(request);
  },
} satisfies ExportedHandler<Env>;
