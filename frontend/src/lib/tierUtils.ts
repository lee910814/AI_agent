export type TierName = 'Iron' | 'Bronze' | 'Silver' | 'Gold' | 'Platinum' | 'Diamond' | 'Master';

export type TierInfo = {
  name: TierName;
  color: string; // Tailwind text color class
  bgColor: string; // Tailwind bg color class
  borderColor: string; // Tailwind border color class
  icon: string; // emoji
};

const TIER_CONFIG: Record<TierName, Omit<TierInfo, 'name'>> = {
  Iron: {
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/20',
    borderColor: 'border-gray-500/30',
    icon: '⚙️',
  },
  Bronze: {
    color: 'text-amber-600',
    bgColor: 'bg-amber-600/20',
    borderColor: 'border-amber-600/30',
    icon: '🥉',
  },
  Silver: {
    color: 'text-slate-300',
    bgColor: 'bg-slate-400/20',
    borderColor: 'border-slate-400/30',
    icon: '🥈',
  },
  Gold: {
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-400/20',
    borderColor: 'border-yellow-400/30',
    icon: '🥇',
  },
  Platinum: {
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-400/20',
    borderColor: 'border-cyan-400/30',
    icon: '💠',
  },
  Diamond: {
    color: 'text-blue-400',
    bgColor: 'bg-blue-400/20',
    borderColor: 'border-blue-400/30',
    icon: '💎',
  },
  Master: {
    color: 'text-purple-400',
    bgColor: 'bg-purple-400/20',
    borderColor: 'border-purple-400/30',
    icon: '👑',
  },
};

export function getTierInfo(tier: string): TierInfo {
  const name = (TIER_CONFIG[tier as TierName] ? tier : 'Iron') as TierName;
  return { name, ...TIER_CONFIG[name] };
}

export function getTierFromElo(elo: number): TierName {
  if (elo >= 2050) return 'Master';
  if (elo >= 1900) return 'Diamond';
  if (elo >= 1750) return 'Platinum';
  if (elo >= 1600) return 'Gold';
  if (elo >= 1450) return 'Silver';
  if (elo >= 1300) return 'Bronze';
  return 'Iron';
}
