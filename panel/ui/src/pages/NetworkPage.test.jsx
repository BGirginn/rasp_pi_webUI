import { describe, expect, it } from 'vitest';
import { formatQueryLogTime, getQueryLogDetailRows, getQueryLogStatus, isValidDomain, parseDomainList } from './NetworkPage.jsx';

describe('NetworkPage DNS helpers', () => {
  it('parses comma and newline separated domain lists', () => {
    expect(parseDomainList('Ads.Example.com,\ntracker.example.org\nads.example.com')).toEqual([
      'ads.example.com',
      'tracker.example.org',
    ]);
  });

  it('validates domain names for panel-managed DNS rules', () => {
    expect(isValidDomain('doubleclick.net')).toBe(true);
    expect(isValidDomain('sub.example.co.uk')).toBe(true);
    expect(isValidDomain('not a domain')).toBe(false);
    expect(isValidDomain('-bad.example')).toBe(false);
  });

  it('derives query log blocked and allowed states', () => {
    expect(getQueryLogStatus({ reason: 'FilteredBlackList' })).toMatchObject({
      blocked: true,
      label: 'Blocked',
      reason: 'FilteredBlackList',
    });
    expect(getQueryLogStatus({ reason: 'NotFilteredNotFound' })).toMatchObject({
      blocked: false,
      label: 'Allowed',
      reason: 'NotFilteredNotFound',
    });
    expect(getQueryLogStatus({ rule: '||ads.example.com^' })).toMatchObject({
      blocked: true,
      label: 'Blocked',
    });
  });

  it('formats query log timestamps without hiding invalid values', () => {
    expect(formatQueryLogTime('not-a-date')).toBe('not-a-date');
    expect(formatQueryLogTime('')).toBe('---');
  });

  it('builds query log detail rows from common AdGuard fields', () => {
    const rows = getQueryLogDetailRows({
      time: '2026-05-11T18:00:00Z',
      client: '192.168.0.107',
      client_proto: 'udp',
      question: { name: 'ads.example.com', type: 'A', class: 'IN' },
      reason: 'FilteredBlackList',
      rule: '||ads.example.com^',
      filterId: 1,
      upstream: 'https://security.cloudflare-dns.com/dns-query',
      elapsedMs: 12,
      answer: [{ type: 'A', value: '0.0.0.0' }],
    });

    expect(rows).toContainEqual(['Client', '192.168.0.107']);
    expect(rows).toContainEqual(['Domain', 'ads.example.com']);
    expect(rows).toContainEqual(['Rule', '||ads.example.com^']);
    expect(rows).toContainEqual(['Answers', '1']);
  });
});
