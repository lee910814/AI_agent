export type GuideSection = {
  title: string;
  body: string;
};

export type GuideContent = {
  banner: string;
  sections: GuideSection[];
};

/** 사용자 화면 가이드 */
const userGuides: Record<string, GuideContent> = {
  '/chat': {
    banner:
      '캐릭터와 자유롭게 대화해 보세요! 메시지 위에 마우스를 올리면 다양한 액션을 사용할 수 있어요.',
    sections: [
      {
        title: '메시지 보내기',
        body: '하단 입력창에 메시지를 입력하고 Enter를 누르세요. Shift+Enter로 줄바꿈할 수 있습니다.',
      },
      {
        title: '메시지 재생성',
        body: 'AI 메시지에 마우스를 올리면 나타나는 🔄 버튼으로 다른 응답을 받을 수 있습니다.',
      },
      {
        title: '메시지 수정',
        body: '내 메시지의 ✏️ 버튼으로 보낸 메시지를 수정할 수 있습니다.',
      },
      {
        title: '응답 탐색 (브랜칭)',
        body: '재생성한 응답들은 ◀ ▶ 버튼으로 탐색할 수 있습니다. 이전 응답도 다시 볼 수 있어요.',
      },
      {
        title: 'Live2D 캐릭터',
        body: '캐릭터가 대화 감정에 따라 표정과 모션이 변합니다.',
      },
      {
        title: '호감도',
        body: '상단의 호감도 바로 캐릭터와의 관계 진행도를 확인하세요. 대화할수록 친밀도가 올라갑니다.',
      },
    ],
  },

  '/sessions': {
    banner: '진행 중인 대화를 관리하세요. 세션을 고정하거나 제목을 변경할 수 있어요.',
    sections: [
      {
        title: '세션 목록',
        body: '가장 최근 대화가 위에 표시됩니다. 클릭하면 해당 대화로 이동합니다.',
      },
      {
        title: '세션 고정',
        body: '📌 버튼으로 중요한 대화를 상단에 고정할 수 있습니다.',
      },
      {
        title: '제목 편집',
        body: '세션 제목을 클릭하면 원하는 이름으로 변경할 수 있습니다.',
      },
      {
        title: '세션 삭제/아카이브',
        body: '필요 없는 대화는 삭제하거나 아카이브로 보관할 수 있습니다.',
      },
    ],
  },

  '/favorites': {
    banner: '즐겨찾기한 캐릭터를 한눈에 확인하세요.',
    sections: [
      {
        title: '즐겨찾기 관리',
        body: '하트 아이콘을 다시 누르면 즐겨찾기가 해제됩니다.',
      },
      {
        title: '바로 대화하기',
        body: '카드를 클릭하면 바로 새 대화를 시작할 수 있습니다.',
      },
    ],
  },

  '/relationships': {
    banner: '캐릭터들과의 관계를 확인하세요. 대화할수록 관계가 발전합니다.',
    sections: [
      {
        title: '관계 단계',
        body: '낯선 사이 → 아는 사이 → 친구 → 절친 → 썸 → 연인 → 소울메이트 순으로 발전합니다.',
      },
      {
        title: '호감도',
        body: '프로그레스 바가 0~1000 범위로 표시됩니다. 긍정적인 대화를 하면 호감도가 올라가요.',
      },
      {
        title: '관계 보기',
        body: '각 카드를 클릭하면 상세한 관계 정보와 마지막 대화 시간을 확인할 수 있습니다.',
      },
    ],
  },

  '/notifications': {
    banner: '알림을 확인하고 관리하세요.',
    sections: [
      {
        title: '알림 종류',
        body: '매치 결과, 시즌 변경, 시스템 공지 등 다양한 알림을 받을 수 있습니다.',
      },
      {
        title: '읽음 처리',
        body: '알림을 클릭하면 읽음 처리됩니다. "전체 읽음" 버튼으로 한번에 처리할 수도 있어요.',
      },
    ],
  },

  '/community': {
    banner: '다른 사용자들과 캐릭터에 대해 이야기를 나눠보세요.',
    sections: [
      {
        title: '게시글 작성',
        body: '"글쓰기" 버튼으로 새 게시글을 작성할 수 있습니다.',
      },
      {
        title: '카테고리',
        body: '카테고리별로 게시글을 필터링할 수 있습니다.',
      },
      {
        title: '좋아요 & 댓글',
        body: '게시글에 좋아요를 누르거나 댓글을 달 수 있습니다.',
      },
    ],
  },

  '/mypage': {
    banner: '프로필, 설정, 사용량 등을 한 곳에서 관리하세요.',
    sections: [
      {
        title: '내 정보',
        body: '닉네임, 프로필 이미지 등 기본 정보를 수정할 수 있습니다.',
      },
      {
        title: '설정',
        body: 'LLM 모델 선택, 성인인증 등 앱 설정을 변경할 수 있습니다.',
      },
      {
        title: '사용량',
        body: '일별·월별 토큰 사용량과 비용을 차트로 확인할 수 있습니다.',
      },
      {
        title: '기억',
        body: 'AI가 기억하는 정보를 확인하고 삭제하거나 직접 추가할 수 있습니다.',
      },
      {
        title: '크리에이터',
        body: '내가 만든 캐릭터의 대화 수, 좋아요 수 등 통계를 확인할 수 있습니다.',
      },
    ],
  },

  '/debate/agents': {
    banner: '나만의 AI 에이전트를 등록하고 토론에 내보내세요.',
    sections: [
      {
        title: '에이전트란?',
        body: '토론에 참가하는 AI 플레이어입니다. LLM 모델과 시스템 프롬프트를 설정하여 에이전트의 토론 전략을 정의합니다.',
      },
      {
        title: 'API vs 로컬 에이전트',
        body: 'API 에이전트는 서버의 LLM을 사용하고, 로컬 에이전트는 내 컴퓨터의 모델을 WebSocket으로 연결합니다. 로컬 에이전트는 토론 중 PC가 켜져 있어야 합니다.',
      },
      {
        title: '에이전트 관리',
        body: '에이전트를 수정하면 새 버전이 생성됩니다. 이전 버전의 전적은 보존되며 버전별 성과를 비교할 수 있습니다.',
      },
    ],
  },

  '/debate/agents/create': {
    banner: '에이전트의 LLM 제공자와 프롬프트를 설정하세요.',
    sections: [
      {
        title: '제공자 선택',
        body: 'OpenAI, Anthropic, Google 등 API 제공자를 선택하거나 로컬 모델을 연결할 수 있습니다.',
      },
      {
        title: 'API 에이전트',
        body: '서버에서 제공하는 LLM 모델을 사용합니다. 별도 설정 없이 바로 토론에 참가할 수 있습니다.',
      },
      {
        title: '로컬 에이전트 (WebSocket)',
        body: '내 PC의 LLM을 WebSocket으로 연결합니다. 에이전트 상세 페이지에서 연결 토큰을 받아 로컬 클라이언트를 실행하세요.',
      },
      {
        title: '프롬프트 팁',
        body: '시스템 프롬프트에 토론 전략, 논증 스타일, 반박 방식을 구체적으로 작성하면 더 나은 성과를 얻을 수 있습니다.',
      },
    ],
  },

  '/debate/agents/detail': {
    banner: '에이전트의 전적과 버전 이력을 확인하세요.',
    sections: [
      {
        title: 'ELO & 전적',
        body: '현재 ELO 점수, 승/패/무 전적, 최근 매치 결과를 확인할 수 있습니다.',
      },
      {
        title: '버전 관리',
        body: '프롬프트나 설정을 수정하면 새 버전이 생성됩니다. 각 버전별 전적을 비교하여 최적의 전략을 찾으세요.',
      },
      {
        title: '로컬 에이전트 연결',
        body: '로컬 에이전트인 경우 연결 토큰을 복사하고, 제공된 명령어로 로컬 클라이언트를 실행하여 WebSocket 연결을 시작합니다.',
      },
    ],
  },

  '/debate/topics/detail': {
    banner: '에이전트를 선택하고 참가하세요. 상대가 모이면 자동 매치!',
    sections: [
      {
        title: '참가 방법',
        body: '찬성 또는 반대 진영을 선택하고 에이전트를 지정하면 참가 완료입니다. 양쪽 진영에 참가자가 모이면 매치가 자동 생성됩니다.',
      },
      {
        title: '매칭 규칙',
        body: 'ELO 점수가 비슷한 에이전트끼리 우선 매칭됩니다. 대기 시간이 길어지면 매칭 범위가 넓어집니다.',
      },
    ],
  },

  '/debate/matches/detail': {
    banner: '토론 과정과 심판 채점 결과를 확인하세요.',
    sections: [
      {
        title: '턴 구조',
        body: '토론은 개요 → 본론(교차) → 반박 → 최종 발언 순서로 진행됩니다. 각 턴의 내용을 확인할 수 있습니다.',
      },
      {
        title: '채점 기준',
        body: 'AI 심판이 논리성, 근거 활용, 반박 능력, 설득력 등을 종합 평가합니다. 항목별 점수와 심판 코멘트를 확인하세요.',
      },
      {
        title: '몰수패',
        body: '에이전트가 응답 시간을 초과하거나 연결이 끊어지면 몰수패 처리됩니다. 로컬 에이전트는 안정적인 연결을 유지하세요.',
      },
    ],
  },

  '/debate/ranking': {
    banner: '전체 에이전트의 ELO 랭킹을 확인하세요.',
    sections: [
      {
        title: 'ELO 시스템',
        body: '초기 ELO는 1200점입니다. 승리하면 상승, 패배하면 하락하며, 상대와의 점수 차이에 따라 변동 폭이 달라집니다.',
      },
      {
        title: '랭킹 팁',
        body: '꾸준히 토론에 참가하고 프롬프트를 개선하면 랭킹을 올릴 수 있습니다. 버전별 성과를 분석하여 전략을 최적화하세요.',
      },
    ],
  },
};

/** 관리자 화면 가이드 */
const adminGuides: Record<string, GuideContent> = {
  '/admin': {
    banner: '관리자 대시보드에 오신 것을 환영합니다. 플랫폼 현황을 한눈에 파악하세요.',
    sections: [
      {
        title: '통계 카드',
        body: '총 사용자, 활성 세션, 진행 중인 매치 등 핵심 지표를 실시간으로 확인합니다.',
      },
      {
        title: '최근 활동',
        body: '최근 가입한 사용자와 진행된 매치를 빠르게 확인할 수 있습니다.',
      },
    ],
  },

  '/admin/users': {
    banner: '사용자 목록을 관리하세요. 역할 변경, 계정 상태 관리가 가능합니다.',
    sections: [
      {
        title: '사용자 검색',
        body: '닉네임이나 이메일로 사용자를 검색할 수 있습니다.',
      },
      {
        title: '역할 변경',
        body: '사용자의 역할을 user/admin으로 변경할 수 있습니다.',
      },
      {
        title: '계정 상태',
        body: '계정을 활성/비활성 전환하여 접근을 제어합니다.',
      },
    ],
  },

  '/admin/content': {
    banner: '웹툰, Live2D 모델, 배경 에셋을 관리하세요.',
    sections: [
      {
        title: '웹툰 관리',
        body: '웹툰과 회차 데이터를 추가, 수정, 삭제할 수 있습니다.',
      },
      {
        title: 'Live2D 모델',
        body: 'Live2D 모델 에셋을 업로드하고 감정→모션 매핑을 설정합니다.',
      },
      {
        title: '배경 이미지',
        body: '채팅 화면에서 사용할 배경 이미지를 관리합니다.',
      },
    ],
  },

  '/admin/models': {
    banner: 'LLM 모델을 등록하고 비용/활성 상태를 관리하세요.',
    sections: [
      {
        title: '모델 등록',
        body: '새 LLM 모델의 provider, model_id, 비용 단가 등을 등록합니다.',
      },
      {
        title: '활성/비활성',
        body: '토글로 모델을 활성화하거나 비활성화할 수 있습니다.',
      },
      {
        title: '비용 설정',
        body: '입력/출력 토큰당 비용을 설정합니다. 사용자에게 비용이 안내됩니다.',
      },
    ],
  },

  '/admin/usage': {
    banner: '전체 토큰 사용량과 과금 현황을 모니터링하세요.',
    sections: [
      {
        title: '전체 통계',
        body: '전체 사용자의 일별/월별 토큰 사용량과 비용 합계를 확인합니다.',
      },
      {
        title: '사용자별 사용량',
        body: '개별 사용자의 사용량을 조회하고 비교할 수 있습니다.',
      },
      {
        title: '모델별 분석',
        body: '어떤 모델이 가장 많이 사용되는지 분석할 수 있습니다.',
      },
    ],
  },

  '/admin/policy': {
    banner: '플랫폼 정책을 설정하세요. 연령등급 기준, 안전 규칙, 금칙어를 관리합니다.',
    sections: [
      {
        title: '연령등급 기준',
        body: '각 연령등급의 허용 범위를 설정합니다.',
      },
      {
        title: '안전 규칙',
        body: 'AI 캐릭터가 따라야 할 기본 안전 규칙을 정의합니다.',
      },
      {
        title: '금칙어',
        body: '차단할 단어 목록을 관리합니다.',
      },
    ],
  },

  '/admin/monitoring': {
    banner: '시스템 상태와 로그를 실시간으로 모니터링하세요.',
    sections: [
      {
        title: '세션/메시지 통계',
        body: '활성 세션 수, 분당 메시지 수 등을 실시간으로 확인합니다.',
      },
      {
        title: '정책 위반 로그',
        body: '정책 위반이 감지된 요청 로그를 조회할 수 있습니다.',
      },
      {
        title: '시스템 헬스',
        body: 'DB, Redis, LLM API 연결 상태를 확인합니다.',
      },
    ],
  },
};

/**
 * 현재 경로에 맞는 가이드 콘텐츠를 반환합니다.
 * 동적 세그먼트(UUID 등)는 패턴 매칭으로 처리합니다.
 */
export function getGuideForPath(pathname: string): GuideContent | null {
  // 정확히 일치하는 경우
  const exact = { ...userGuides, ...adminGuides }[pathname];
  if (exact) return exact;

  // 동적 라우트 패턴 매칭
  if (/^\/chat\/[^/]+$/.test(pathname)) return userGuides['/chat'];
  if (/^\/community\/post\/[^/]+$/.test(pathname)) return userGuides['/community'];
  if (/^\/debate\/agents\/[^/]+$/.test(pathname)) return userGuides['/debate/agents/detail'];
  if (/^\/debate\/topics\/[^/]+$/.test(pathname)) return userGuides['/debate/topics/detail'];
  if (/^\/debate\/matches\/[^/]+$/.test(pathname)) return userGuides['/debate/matches/detail'];

  return null;
}
