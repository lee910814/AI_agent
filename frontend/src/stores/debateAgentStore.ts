import { create } from 'zustand';
import { api } from '@/lib/api';
import type {
  DebateAgent,
  AgentVersion,
  SliderField,
  SelectField,
  FreeTextField,
  CustomizationSchema,
  AgentTemplate,
} from '@/types/debate';

type CreateAgentPayload = {
  name: string;
  description?: string;
  provider: string;
  model_id?: string;
  api_key?: string;
  system_prompt?: string;
  version_tag?: string;
  parameters?: Record<string, unknown>;
  image_url?: string;
  use_platform_credits?: boolean;
  // 템플릿 기반 생성 필드
  template_id?: string;
  customizations?: Record<string, unknown>;
  enable_free_text?: boolean;
  is_profile_public?: boolean;
};

type UpdateAgentPayload = Partial<CreateAgentPayload>;

type DebateAgentState = {
  agents: DebateAgent[];
  templates: AgentTemplate[];
  loading: boolean;
  fetchMyAgents: () => Promise<void>;
  fetchTemplates: () => Promise<void>;
  createAgent: (data: CreateAgentPayload) => Promise<DebateAgent>;
  updateAgent: (id: string, data: UpdateAgentPayload) => Promise<DebateAgent>;
  deleteAgent: (id: string) => Promise<void>;
  fetchVersions: (agentId: string) => Promise<AgentVersion[]>;
};

export const useDebateAgentStore = create<DebateAgentState>((set) => ({
  agents: [],
  templates: [],
  loading: false,
  fetchMyAgents: async () => {
    set({ loading: true });
    try {
      const data = await api.get<DebateAgent[]>('/agents/me');
      set({ agents: data });
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchTemplates: async () => {
    try {
      const data = await api.get<AgentTemplate[]>('/agents/templates');
      set({ templates: data });
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  },
  createAgent: async (data) => {
    const agent = await api.post<DebateAgent>('/agents', data);
    set((s) => ({ agents: [agent, ...s.agents] }));
    return agent;
  },
  updateAgent: async (id, data) => {
    const agent = await api.put<DebateAgent>(`/agents/${id}`, data);
    set((s) => ({ agents: s.agents.map((a) => (a.id === id ? agent : a)) }));
    return agent;
  },
  deleteAgent: async (id) => {
    await api.delete(`/agents/${id}`);
    set((s) => ({ agents: s.agents.filter((a) => a.id !== id) }));
  },
  fetchVersions: async (agentId) => {
    return api.get<AgentVersion[]>(`/agents/${agentId}/versions`);
  },
}));

export type {
  DebateAgent,
  AgentVersion,
  AgentTemplate,
  CustomizationSchema,
  SliderField,
  SelectField,
  FreeTextField,
  CreateAgentPayload,
};
