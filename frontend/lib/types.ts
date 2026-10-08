export type Num = number | null | undefined;

export interface PlayerCard {
  slug: string;
  name: string;
  lineup_slot: string;
  agent: string;
  focus_areas: string[];
  data_available: boolean;
  career_years?: string;
  seasons_played?: number;
  position?: string;
  height_in?: number;
  teams?: string[];
  archetypes?: string[];
  achievements?: { label: string; count: number }[];
  career_stats?: { pts_per_g: Num; trb_per_g: Num; ast_per_g: Num; ts_pct: Num; games: Num };
  peak_seasons?: string[];
}

export interface PlayersResponse {
  disclaimer: string;
  lineup: Record<string, string>;
  players: PlayerCard[];
}

export interface Achievement {
  achievement_type: string;
  label: string;
  count: number;
  seasons: string[];
}

export interface Archetype {
  archetype: string;
  status: "supported" | "not_supported" | "insufficient_data";
  score: Num;
  evidence: string[];
  rule: string;
}

export interface Phase {
  phase_type: "team_stint" | "statistical";
  name: string;
  start_season: string;
  end_season: string;
  seasons: string[];
  summary?: { per_game?: Record<string, Num>; shooting?: Record<string, Num>; advanced?: Record<string, Num> };
}

export interface PeakSeason {
  season: string;
  peak_score: number;
  components: Record<string, Num>;
}

export interface Summary {
  num_seasons?: number;
  totals?: Record<string, Num>;
  per_game?: Record<string, Num>;
  per36?: Record<string, Num>;
  shooting?: Record<string, Num>;
  advanced?: Record<string, Num>;
}

export interface Profile {
  card: PlayerCard;
  identity: Record<string, any>;
  career_summary: { regular_season: Summary };
  playoff_summary: Summary;
  finals_summary: { nba_finals?: any; conference_finals?: any; series?: any[] };
  achievements: Achievement[];
  records: { key: string; label: string; value: Num }[];
  shot_profile_summary: Record<string, any>;
  play_type_tendencies: Record<string, { frequency: number; ppp: number; percentile: number; seasons: string[] }>;
  clutch_summary: Record<string, any> | null;
  career_phases: Phase[];
  peak_seasons: PeakSeason[];
  peak_formula?: string;
  archetypes: Archetype[];
  strengths: { label: string; evidence: string }[];
  limitations: { label: string; evidence: string }[];
  data_limitations: string[];
}

export interface SeasonLine {
  season: string;
  team: string | null;
  teams: string[] | null;
  age: Num;
  per_game: Record<string, Num>;
  advanced: Record<string, Num>;
  shooting: Record<string, Num>;
  awards_text?: string | null;
  peak_score?: Num;
  provenance?: { source?: string; source_url?: string; retrieved_at?: string };
}

export interface CareerResponse {
  player: string;
  regular_season: SeasonLine[];
  playoffs: SeasonLine[];
  peak_scores: PeakSeason[];
}

export interface DataConsidered {
  layers?: string[];
  sections?: string[];
  retrieved_documents?: { title: string; topics?: string[]; score?: number }[];
  peak_seasons?: string[];
  retrieval_intents?: string[];
  approx_tokens?: number;
}

export interface SimMessage {
  round: number;
  slug: string;
  player: string;
  content: Record<string, any>;
  data_considered?: DataConsidered;
  model?: string;
  latency_ms?: number;
}

export interface CourtStep {
  time: number;
  player: string;
  action: string;
  target?: string;
  location?: string | null;
  destination?: string | null;
}

export interface PlayCall {
  play_name?: string;
  ball_handler?: string;
  primary_option?: string;
  secondary_option?: string;
  third_option?: string;
  counter?: string;
  player_roles?: Record<string, string>;
  off_ball_actions?: string[];
}

export interface CoachDecisionT {
  verdict?: string;
  answer?: string;
  play?: PlayCall | null;
  play_name?: string;
  ball_handler?: string;
  inbounder?: string | null;
  primary_option?: string;
  secondary_option?: string;
  third_option?: string;
  counter?: string;
  player_roles?: Record<string, string>;
  off_ball_actions?: string[];
  reasoning?: string;
  key_data_points?: string[];
  career_data_considered?: string[];
  rejected_alternatives?: { proposal?: string; proposed_by?: string; reason?: string }[];
  vote_summary?: string;
  confidence?: number;
  court?: null | {
    start_positions?: Record<string, string | null>;
    ball_starts_with?: string;
    play_sequence?: CourtStep[];
  };
  parse_error?: boolean;
  raw?: string;
}

export interface Simulation {
  id: string;
  created_at?: string;
  status: string;
  scenario: Record<string, any>;
  llm_config?: Record<string, any>;
  error?: string | null;
  rounds: { round_number: number; name: string; started_at?: string; completed_at?: string | null }[];
  messages: SimMessage[];
  coach_decision: { decision: CoachDecisionT; model?: string } | null;
  disclaimer?: string;
  /** "steps": the browser drives each round (hosted on Vercel); "background": the server runs them all. */
  run_mode?: "steps" | "background";
  ran_stage?: number | null;
}

export interface SiteConfig {
  run_mode: "steps" | "background";
  default_provider: string;
  providers: string[];
  access_code_required: boolean;
  daily_limit: number | null;
}

export interface PromptPlayer {
  slug: string;
  name: string;
  agent_name: string;
  lineup_slot: string;
  focus_areas: string[];
  data_available: boolean;
  archetypes?: string[];
  not_testable?: string[];
  strengths?: string[];
  limitations?: string[];
  peak_seasons?: string[];
  layer1_tokens?: number;
  layer2_tokens?: number;
  context_tokens_sent?: number;
  layers_sent?: string[];
  retrieved_for_sample?: { title: string; score?: number }[];
  layer1_text?: string;
}

export interface PromptsResponse {
  sample: { question: string; intents: string[]; topics: string[] };
  templates: Record<"player_system" | "round1" | "round2" | "round3" | "coach_system" | "coach_user" | "grounding_rules" | "coach_rules", string>;
  models: Record<string, string>;
  context_token_budget: number;
  players: PromptPlayer[];
}
