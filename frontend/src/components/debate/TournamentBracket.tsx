'use client';

type MatchEntry = {
  id: string;
  agent_a_name?: string;
  agent_b_name?: string;
  winner_id?: string | null;
  agent_a_id?: string;
  agent_b_id?: string;
  tournament_round: number;
};

type Props = {
  entries: { agent_id: string; agent_name: string; seed: number }[];
  matches: MatchEntry[];
  rounds: number;
};

export function TournamentBracket({ entries, matches, rounds }: Props) {
  const agentMap = Object.fromEntries(entries.map((e) => [e.agent_id, e.agent_name]));

  const roundNumbers = Array.from(new Set(matches.map((m) => m.tournament_round))).sort(
    (a, b) => a - b,
  );

  if (roundNumbers.length === 0) {
    return (
      <div className="text-center text-text-muted py-8 text-sm">아직 진행된 라운드가 없습니다.</div>
    );
  }

  return (
    <div className="flex gap-6 overflow-x-auto pb-4">
      {roundNumbers.map((round) => {
        const roundMatches = matches.filter((m) => m.tournament_round === round);
        const roundLabel =
          round === rounds ? '결승' : round === rounds - 1 ? '준결승' : `${round}라운드`;
        return (
          <div key={round} className="flex flex-col gap-4 min-w-[200px]">
            <div className="text-xs text-text-muted uppercase tracking-wide font-semibold text-center">
              {roundLabel}
            </div>
            {roundMatches.map((match) => {
              const aName = match.agent_a_id ? (agentMap[match.agent_a_id] ?? '?') : 'TBD';
              const bName = match.agent_b_id ? (agentMap[match.agent_b_id] ?? '?') : 'TBD';
              const aWon = match.winner_id && match.winner_id === match.agent_a_id;
              const bWon = match.winner_id && match.winner_id === match.agent_b_id;
              return (
                <div
                  key={match.id}
                  className="bg-bg-surface border border-border rounded-xl overflow-hidden"
                >
                  <div
                    className={`px-3 py-2 text-sm border-b border-border/50 flex justify-between ${
                      aWon ? 'text-yellow-400 font-semibold' : 'text-text-muted'
                    }`}
                  >
                    <span className="truncate">{aName}</span>
                    {aWon && <span className="text-xs ml-2">🏆</span>}
                  </div>
                  <div
                    className={`px-3 py-2 text-sm flex justify-between ${
                      bWon ? 'text-yellow-400 font-semibold' : 'text-text-muted'
                    }`}
                  >
                    <span className="truncate">{bName}</span>
                    {bWon && <span className="text-xs ml-2">🏆</span>}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
