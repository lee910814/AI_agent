import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AgentConnectionGuide } from './AgentConnectionGuide';

// Mock clipboard API
Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

describe('AgentConnectionGuide', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render connection status as active when connected', () => {
    render(<AgentConnectionGuide agentId="agent-1" isConnected={true} />);
    expect(screen.getByText(/활성/)).toBeInTheDocument();
  });

  it('should render connection status as waiting when disconnected', () => {
    render(<AgentConnectionGuide agentId="agent-1" isConnected={false} />);
    expect(screen.getByText(/대기 중/)).toBeInTheDocument();
  });

  it('should display WebSocket endpoint URL', () => {
    render(<AgentConnectionGuide agentId="test-agent-id" isConnected={false} />);
    const matches = screen.getAllByText(/ws:\/\/.*\/ws\/agent\/test-agent-id/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('should show JWT token section', () => {
    render(<AgentConnectionGuide agentId="agent-1" isConnected={false} />);
    expect(screen.getByText('JWT 토큰')).toBeInTheDocument();
  });

  it('should show login required when no token', () => {
    render(<AgentConnectionGuide agentId="agent-1" isConnected={false} />);
    expect(screen.getByText('(로그인 필요)')).toBeInTheDocument();
  });

  it('should render agent run step', () => {
    render(<AgentConnectionGuide agentId="agent-1" isConnected={false} />);
    expect(screen.getByText('에이전트 실행')).toBeInTheDocument();
  });

  it('should have copy buttons', () => {
    render(<AgentConnectionGuide agentId="agent-1" isConnected={false} />);
    const copyButtons = screen.getAllByTitle(/복사/);
    expect(copyButtons.length).toBeGreaterThanOrEqual(2);
  });
});
