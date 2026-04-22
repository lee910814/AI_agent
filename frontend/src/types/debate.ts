// 중앙화된 토론 플랫폼 타입 정의
// debateStore, debateAgentStore, debateTournamentStore에서 이동됨

// ─── debateStore 출처 타입 ────────────────────────────────────────────────────

export type AgentSummary = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  image_url?: string | null;
};

export type DebateTopic = {
  id: string;
  title: string;
  description: string | null;
  mode: string;
  status: string;
  max_turns: number;
  turn_token_limit: number;
  scheduled_start_at: string | null;
  scheduled_end_at: string | null;
  is_admin_topic: boolean;
  tools_enabled: boolean;
  queue_count: number;
  match_count: number;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  creator_nickname: string | null;
  is_password_protected?: boolean;
};

export type PromotionSeries = {
  id?: string;
  agent_id?: string;
  series_type: 'promotion' | 'demotion';
  from_tier: string;
  to_tier: string;
  required_wins: number;
  current_wins: number;
  current_losses: number;
  status: 'active' | 'won' | 'lost' | 'cancelled' | 'expired';
  created_at: string;
  completed_at: string | null;
};

export type DebateMatch = {
  id: string;
  topic_id: string;
  topic_title: string;
  agent_a: AgentSummary;
  agent_b: AgentSummary;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'waiting_agent' | 'forfeit';
  winner_id: string | null;
  score_a: number;
  score_b: number;
  penalty_a: number;
  penalty_b: number;
  turn_count?: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  elo_a_before?: number | null;
  elo_b_before?: number | null;
  elo_a_after?: number | null;
  elo_b_after?: number | null;
  match_type?: 'ranked' | 'promotion' | 'demotion';
  series_id?: string | null;
};

export type TurnLog = {
  id: string;
  turn_number: number;
  speaker: string;
  agent_id: string;
  action: string;
  claim: string;
  evidence: string | null;
  tool_used: string | null;
  tool_result: string | null;
  penalties: Record<string, number> | null;
  penalty_total: number;
  human_suspicion_score: number;
  response_time_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  review_result: {
    logic_score: number;
    violations: { type: string; severity: string; detail: string }[];
    feedback: string;
    blocked: boolean;
    skipped?: boolean;
  } | null;
  is_blocked: boolean;
  created_at: string;
};

export type TurnReview = {
  turn_number: number;
  speaker: string;
  logic_score: number | null;
  violations: { type: string; severity: string; detail: string }[];
  feedback: string;
  blocked: boolean;
  skipped?: boolean;
};

export type PredictionStats = {
  a_win: number;
  b_win: number;
  draw: number;
  total: number;
  my_prediction: 'a_win' | 'b_win' | 'draw' | null;
  is_correct: boolean | null;
};

export type StreamingTurn = {
  turn_number: number;
  speaker: string;
  raw: string;
};

export type RankingEntry = {
  id: string;
  name: string;
  owner_nickname: string;
  owner_id: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url?: string | null;
  tier?: string;
  is_profile_public?: boolean;
};

export type TopicCreatePayload = {
  title: string;
  description?: string | null;
  mode?: string;
  max_turns?: number;
  turn_token_limit?: number;
  tools_enabled?: boolean;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  password?: string | null;
};

// ─── debateAgentStore 출처 타입 ──────────────────────────────────────────────

export type SliderField = {
  key: string;
  label: string;
  min: number;
  max: number;
  default: number;
  description: string;
};

type SelectOption = { value: string; label: string };

export type SelectField = {
  key: string;
  label: string;
  options: SelectOption[];
  default: string;
};

export type FreeTextField = {
  key: string;
  label: string;
  placeholder: string;
  max_length: number;
};

export type CustomizationSchema = {
  sliders: SliderField[];
  selects: SelectField[];
  free_text?: FreeTextField;
};

export type AgentTemplate = {
  id: string;
  slug: string;
  display_name: string;
  description: string | null;
  icon: string | null;
  customization_schema: CustomizationSchema;
  default_values: Record<string, unknown>;
  sort_order: number;
  is_active: boolean;
};

export type DebateAgent = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  provider: string;
  model_id: string;
  image_url: string | null;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  is_active: boolean;
  is_connected: boolean;
  is_system_prompt_public: boolean;
  use_platform_credits: boolean;
  tier: string;
  tier_protection_count: number;
  active_series_id: string | null;
  is_profile_public: boolean;
  name_changed_at: string | null;
  template_id: string | null;
  customizations: Record<string, unknown> | null;
  // 팔로우 시스템 (백엔드 GET /agents/{id} 응답에 포함)
  follower_count: number;
  is_following: boolean;
  created_at: string;
  updated_at: string;
};

export type AgentVersion = {
  id: string;
  version_number: number;
  version_tag: string | null;
  system_prompt: string;
  parameters: Record<string, unknown> | null;
  wins: number;
  losses: number;
  draws: number;
  created_at: string;
};

// ─── debateTournamentStore 출처 타입 ─────────────────────────────────────────

export type Tournament = {
  id: string;
  title: string;
  topic_id: string;
  status: 'registration' | 'in_progress' | 'completed' | 'cancelled';
  bracket_size: number;
  current_round: number;
  winner_agent_id: string | null;
  created_at: string;
};

export type TournamentEntry = {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_image_url: string | null;
  seed: number;
  eliminated_at: string | null;
  eliminated_round: number | null;
};

export type TournamentDetail = Tournament & {
  entries: TournamentEntry[];
};
