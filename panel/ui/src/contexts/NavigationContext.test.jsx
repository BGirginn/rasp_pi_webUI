import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { NavigationProvider, useNavigation } from './NavigationContext';

function NavigationProbe() {
  const { currentPage, setCurrentPage } = useNavigation();
  return <><output>{currentPage}</output><button onClick={() => setCurrentPage('files')}>Open files</button></>;
}
beforeEach(() => window.history.replaceState(null, '', '/'));

describe('persistent page navigation', () => {
  it('opens the bookmarked page and preserves it after remount', () => {
    window.history.replaceState(null, '', '/#/services');
    const first = render(<NavigationProvider><NavigationProbe /></NavigationProvider>);
    expect(screen.getByText('services')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open files' }));
    expect(window.location.hash).toBe('#/files');
    first.unmount();
    render(<NavigationProvider><NavigationProbe /></NavigationProvider>);
    expect(screen.getByText('files')).toBeInTheDocument();
  });
  it('tracks back/forward changes and normalizes unknown pages', () => {
    render(<NavigationProvider><NavigationProbe /></NavigationProvider>);
    act(() => {
      window.history.replaceState(null, '', '/#/jobs');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    expect(screen.getByText('jobs')).toBeInTheDocument();
    act(() => {
      window.history.replaceState(null, '', '/#/missing');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(screen.getByText('dashboard')).toBeInTheDocument();
    expect(window.location.hash).toBe('#/dashboard');
  });
});
