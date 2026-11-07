import { afterEach, expect, it, vi } from 'vitest';
import {
  ingestDocument,
  answerQuestion,
} from '../../src/services/api/adapters/hamtayarAdapter';
import { diagnose } from '../../src/services/operations/operationService';
const config = {
  baseUrl: 'http://localhost:8000',
  timeoutMs: 100,
  maxUploadBytes: 1000,
  uploadLimitVerified: true,
};
afterEach(() => vi.restoreAllMocks());
it('sends the actual File with automatic API identifiers and preserves null chunk counts', async () => {
  const file = new File(['actual file contents'], 'a.txt', { type: 'text/plain' });
  const spy = vi.spyOn(window, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        status: 'completed',
        source_id: 'source',
        version: '1',
        chunks_indexed: null,
      }),
    ),
  );
  const result = await ingestDocument(
    {
      id: '1',
      file,
      version: '1',
      processingProfile: 'default',
      customMetadata: { center: 'alpha' },
    },
    true,
    undefined,
    config,
  );
  const form = spy.mock.calls[0][1]?.body as FormData;
  expect([...form.keys()].sort()).toEqual(
    ['file', 'source_id', 'knowledge_space_id', 'version', 'processing_profile'].sort(),
  );
  expect(form.get('file')).toBe(file);
  expect(form.get('source_id')).toBe('1');
  expect(form.get('knowledge_space_id')).toBe('demo-documents');
  const uploaded = form.get('file') as File;
  const contents = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(uploaded);
  });
  expect(contents).toBe('actual file contents');
  expect(result.chunksIndexed).toBeNull();
  expect(result.requestId).toBeUndefined();
});
it('requires explicit metadata reduction and sends question only', async () => {
  const spy = vi.spyOn(window, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        status: 'no_evidence',
        answer: '',
        citations: [],
        request_id: 'real-id',
      }),
    ),
  );
  await expect(
    ingestDocument(
      {
        id: '1',
        file: new File(['x'], 'a.txt'),
        version: '1',
        processingProfile: 'default',
        customMetadata: { center: 'p' },
      },
      false,
      undefined,
      config,
    ),
  ).rejects.toMatchObject({ kind: 'blocked' });
  expect(spy).not.toHaveBeenCalled();
  const answer = await answerQuestion(' test ', undefined, config);
  expect(spy.mock.calls[0][1]?.body).toBe('{"question":"test"}');
  expect(answer.status).toBe('no_evidence');
});
it.each([401, 422, 413, 500, 503, 504])(
  'distinguishes HTTP %i without leaking the body',
  async (status) => {
    vi.spyOn(window, 'fetch').mockResolvedValue(
      new Response('secret traceback', { status }),
    );
    try {
      await answerQuestion('test', undefined, config);
      throw new Error('expected rejection');
    } catch (error) {
      const diagnostic = diagnose(error);
      expect(diagnostic.statusCode).toBe(status);
      expect(JSON.stringify(diagnostic)).not.toContain('secret');
    }
  },
);
it('rejects invalid responses rather than fabricating answers', async () => {
  vi.spyOn(window, 'fetch').mockResolvedValue(new Response('{}'));
  await expect(answerQuestion('test', undefined, config)).rejects.toMatchObject({
    kind: 'invalid_response',
  });
});
it('distinguishes a network failure from a client timeout', async () => {
  vi.spyOn(window, 'fetch').mockRejectedValueOnce(
    new TypeError('private network detail'),
  );
  await expect(answerQuestion('test', undefined, config)).rejects.toMatchObject({
    kind: 'network',
  });
  vi.spyOn(window, 'fetch').mockImplementation(
    (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('aborted', 'AbortError')),
          { once: true },
        );
      }),
  );
  await expect(
    answerQuestion('test', undefined, { ...config, timeoutMs: 5 }),
  ).rejects.toMatchObject({ kind: 'timeout' });
});
