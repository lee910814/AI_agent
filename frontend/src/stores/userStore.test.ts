import { describe, it, expect, beforeEach } from 'vitest';
import { useUserStore } from './userStore';

const BASE_USER = {
  email: null as string | null,
  createdAt: '2026-01-01T00:00:00Z',
};

describe('useUserStore', () => {
  beforeEach(() => {
    useUserStore.setState({ user: null, token: null });
  });

  it('should start with null user and token', () => {
    const state = useUserStore.getState();
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
  });

  it('should set user', () => {
    const user = {
      ...BASE_USER,
      id: '123',
      login_id: 'testuser',
      nickname: 'testuser',
      role: 'user' as const,
      ageGroup: 'unverified',
      adultVerifiedAt: null,
      preferredLlmModelId: null,
      creditBalance: 0,
      subscriptionPlanKey: null,
    };
    useUserStore.getState().setUser(user);
    expect(useUserStore.getState().user).toEqual(user);
  });

  it('should set token', () => {
    useUserStore.getState().setToken('jwt-token-123');
    expect(useUserStore.getState().token).toBe('jwt-token-123');
  });

  it('should return false for isAdultVerified when user is null', () => {
    expect(useUserStore.getState().isAdultVerified()).toBe(false);
  });

  it('should return false for isAdultVerified when adultVerifiedAt is null', () => {
    useUserStore.getState().setUser({
      ...BASE_USER,
      id: '1',
      login_id: 'test',
      nickname: 'test',
      role: 'user',
      ageGroup: 'unverified',
      adultVerifiedAt: null,
      preferredLlmModelId: null,
      creditBalance: 0,
      subscriptionPlanKey: null,
    });
    expect(useUserStore.getState().isAdultVerified()).toBe(false);
  });

  it('should return true for isAdultVerified when adultVerifiedAt is set', () => {
    useUserStore.getState().setUser({
      ...BASE_USER,
      id: '1',
      login_id: 'test',
      nickname: 'test',
      role: 'user',
      ageGroup: 'adult_verified',
      adultVerifiedAt: '2026-01-01T00:00:00Z',
      preferredLlmModelId: null,
      creditBalance: 0,
      subscriptionPlanKey: null,
    });
    expect(useUserStore.getState().isAdultVerified()).toBe(true);
  });

  it('should return false for isAdmin when user is null', () => {
    expect(useUserStore.getState().isAdmin()).toBe(false);
  });

  it('should return false for isAdmin when role is user', () => {
    useUserStore.getState().setUser({
      ...BASE_USER,
      id: '1',
      login_id: 'test',
      nickname: 'test',
      role: 'user',
      ageGroup: 'unverified',
      adultVerifiedAt: null,
      preferredLlmModelId: null,
      creditBalance: 0,
      subscriptionPlanKey: null,
    });
    expect(useUserStore.getState().isAdmin()).toBe(false);
  });

  it('should return true for isAdmin when role is admin', () => {
    useUserStore.getState().setUser({
      ...BASE_USER,
      id: '1',
      login_id: 'admin',
      nickname: 'admin',
      role: 'admin',
      ageGroup: 'adult_verified',
      adultVerifiedAt: '2026-01-01T00:00:00Z',
      preferredLlmModelId: null,
      creditBalance: 0,
      subscriptionPlanKey: null,
    });
    expect(useUserStore.getState().isAdmin()).toBe(true);
  });

  it('should clear user and token on logout', async () => {
    useUserStore.getState().setUser({
      ...BASE_USER,
      id: '1',
      login_id: 'test',
      nickname: 'test',
      role: 'user',
      ageGroup: 'unverified',
      adultVerifiedAt: null,
      preferredLlmModelId: null,
      creditBalance: 0,
      subscriptionPlanKey: null,
    });
    useUserStore.getState().setToken('token');
    await useUserStore.getState().logout();

    expect(useUserStore.getState().user).toBeNull();
    expect(useUserStore.getState().token).toBeNull();
  });
});
