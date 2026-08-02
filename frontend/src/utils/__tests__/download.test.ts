import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { downloadText } from '../download';

// jsdom doesn't implement createObjectURL/revokeObjectURL.
describe('downloadText', () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    createObjectURL = vi.fn(() => 'blob:mock-url');
    revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('attaches the anchor to the document before clicking it', () => {
    // Firefox/Safari silently no-op a click on a detached element — this is
    // the actual bug being regression-tested, not an implementation detail.
    let wasConnectedAtClick = false;
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        wasConnectedAtClick = this.isConnected;
      });

    downloadText('hello', 'file.csv', 'text/csv');

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(wasConnectedAtClick).toBe(true);
    clickSpy.mockRestore();
  });

  it('removes the anchor from the document after clicking', () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    downloadText('hello', 'file.csv', 'text/csv');
    expect(document.querySelector('a[download="file.csv"]')).not.toBeInTheDocument();
    clickSpy.mockRestore();
  });

  it('sets the anchor href/download from the blob URL and filename', () => {
    let href = '';
    let download = '';
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        href = this.href;
        download = this.download;
      });

    downloadText('hello', 'report.csv', 'text/csv');

    expect(href).toBe('blob:mock-url');
    expect(download).toBe('report.csv');
    clickSpy.mockRestore();
  });

  it('does not revoke the object URL synchronously (before the browser can read it)', () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    downloadText('hello', 'file.csv', 'text/csv');
    expect(revokeObjectURL).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    clickSpy.mockRestore();
  });

  it('builds the blob with the given text and mime type', () => {
    let capturedBlob: Blob | undefined;
    createObjectURL.mockImplementation((blob: Blob) => {
      capturedBlob = blob;
      return 'blob:mock-url';
    });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    downloadText('a,b,c', 'file.csv', 'text/csv');

    expect(capturedBlob).toBeInstanceOf(Blob);
    expect(capturedBlob?.type).toBe('text/csv');
    clickSpy.mockRestore();
  });
});
