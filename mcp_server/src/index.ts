import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ErrorCode,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DATA_PATH = path.join(__dirname, "../../data/secure_health_vault.json");

interface Medication {
  medication: string;
  dosage: string;
  time: string;
  taken_today: boolean;
}

interface FamilyMember {
  id: string;
  name: string;
  current_medications: string[];
  schedule: Medication[];
}

interface Vault {
  family_members: Record<string, FamilyMember>;
  interaction_blacklist: Record<string, string[]>;
  logs: any[];
}

class SafeHealthServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: "safe-health-mcp-server",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupTools();
    
    this.server.onerror = (error) => console.error("[MCP Error]", error);
    process.on("SIGINT", async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  private async readVault(): Promise<Vault> {
    const data = await fs.readFile(DATA_PATH, "utf-8");
    return JSON.parse(data);
  }

  private async writeVault(vault: Vault): Promise<void> {
    await fs.writeFile(DATA_PATH, JSON.stringify(vault, null, 2));
  }

  private setupTools() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: "get_family_member_profile",
          description: "Reads secure_health_vault.json and returns only that member's profile.",
          inputSchema: {
            type: "object",
            properties: {
              member_id: { type: "string" },
            },
            required: ["member_id"],
          },
        },
        {
          name: "check_interaction",
          description: "Checks cross-references in interaction_blacklist.",
          inputSchema: {
            type: "object",
            properties: {
              medication_a: { type: "string" },
              medication_b: { type: "string" },
            },
            required: ["medication_a", "medication_b"],
          },
        },
        {
          name: "log_medication_intake",
          description: "Appends a timestamped object to the logs and sets 'taken_today' to true.",
          inputSchema: {
            type: "object",
            properties: {
              member_id: { type: "string" },
              medication: { type: "string" },
            },
            required: ["member_id", "medication"],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const vault = await this.readVault();

      switch (request.params.name) {
        case "get_family_member_profile": {
          const { member_id } = request.params.arguments as { member_id: string };
          const member = vault.family_members[member_id];
          if (!member) {
            throw new McpError(ErrorCode.InvalidParams, `Member ${member_id} not found`);
          }
          return {
            content: [{ type: "text", text: JSON.stringify(member, null, 2) }],
          };
        }

        case "check_interaction": {
          const { medication_a, medication_b } = request.params.arguments as {
            medication_a: string;
            medication_b: string;
          };
          
          const blacklist_a = vault.interaction_blacklist[medication_a] || [];
          const blacklist_b = vault.interaction_blacklist[medication_b] || [];

          const conflict = blacklist_a.includes(medication_b) || blacklist_b.includes(medication_a);

          return {
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  medication_a,
                  medication_b,
                  has_interaction: conflict,
                  warning: conflict ? `WARNING: Potential interaction detected between ${medication_a} and ${medication_b}!` : "No documented interaction found in local database."
                }, null, 2)
              }
            ],
          };
        }

        case "log_medication_intake": {
          const { member_id, medication } = request.params.arguments as {
            member_id: string;
            medication: string;
          };

          const member = vault.family_members[member_id];
          if (!member) {
            throw new McpError(ErrorCode.InvalidParams, `Member ${member_id} not found`);
          }

          const scheduleItem = member.schedule.find(s => s.medication.toLowerCase() === medication.toLowerCase());
          
          if (scheduleItem) {
            scheduleItem.taken_today = true;
          }

          const logEntry = {
            member_id,
            medication,
            timestamp: new Date().toISOString(),
            status: "taken"
          };

          vault.logs.push(logEntry);
          await this.writeVault(vault);

          return {
            content: [{ type: "text", text: `Successfully logged intake for ${medication} (Member: ${member_id})` }],
          };
        }

        default:
          throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("SafeHealth MCP Server running on stdio");
  }
}

const server = new SafeHealthServer();
server.run().catch(console.error);
