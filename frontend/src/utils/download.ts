/** Trigger a browser download of in-memory text as a file.
 *
 * The anchor must be attached to the document before `.click()` — Firefox
 * and Safari silently ignore a click on a detached element, so a
 * synchronous `revokeObjectURL()` right after `.click()` also risks
 * invalidating the blob URL before the (asynchronous, real-browser) download
 * has actually started reading it. Appending the anchor and deferring the
 * revoke avoids both failure modes; Chrome tolerates either approach, so
 * this doesn't regress it.
 */
export function downloadText(text: string, filename: string, mime: string) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
