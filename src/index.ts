import { Container } from "@cloudflare/containers";

export interface Env {
  ZSCALER_MCP_CONTAINER: DurableObjectNamespace<ZscalerMcpContainer>;
  CONTAINER_INSTANCE_NAME?: string;
}

export class ZscalerMcpContainer extends Container {
  defaultPort = 8000;
  requiredPorts = [8000];
  sleepAfter = "30m";
  enableInternet = true;

  envVars = {
    ZSCALER_MCP_TRANSPORT: "streamable-http",
    ZSCALER_MCP_HOST: "0.0.0.0",
    ZSCALER_MCP_PORT: "8000",
    ZSCALER_MCP_ALLOW_HTTP: "true",
    ZSCALER_MCP_DISABLE_HOST_VALIDATION: "true",
    ZSCALER_MCP_AUTH_ENABLED: "true",
    ZSCALER_MCP_AUTH_MODE: "zscaler",
    ZSCALER_CLOUD: "production",
    ZSCALER_MCP_WRITE_ENABLED: "true",
    ZSCALER_MCP_WRITE_TOOLS: "*",
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/" || url.pathname === "/health" || url.pathname === "/healthz") {
      return Response.json({
        ok: true,
        service: "zscaler-mcp-server",
        mcp_endpoint: `${url.origin}/mcp`,
      });
    }

    const instanceName = env.CONTAINER_INSTANCE_NAME || "zscaler-mcp-v3";
    const container = env.ZSCALER_MCP_CONTAINER.getByName(instanceName);

    await container.startAndWaitForPorts();
    return container.fetch(request);
  },
};
