import assert from 'node:assert/strict';
const modulePath = process.argv[2];
const { extractReadableContent, retainPublicContactContext } = await import(modulePath);
const html = `<html><head><title>Phuket tours</title><script>hidden@example.org</script></head><body>
<nav><a href="/about">About us</a><a href="/contact">Contact us</a></nav>
<article><h1>Phuket packages from India</h1>${'<p>Our agency offers Phuket packages for families.</p>'.repeat(60)}</article>
<footer>Our office in New Delhi. Business enquiries: <a href="mailto:contactus@example.org">Email us</a></footer></body></html>`;
for (const extractMode of ['markdown','text']) {
 const result=await extractReadableContent({html,url:'https://example.org/phuket',extractMode});
 assert.ok(result.text.includes('contactus@example.org'));
 assert.ok(result.text.includes('/contact'));
 assert.ok(result.text.includes('Phuket packages'));
 assert.ok(!result.text.includes('hidden@example.org'));
 assert.ok(result.text.indexOf('contactus@example.org')<1000);
}
assert.equal(retainPublicContactContext('Article','<p>Ordinary text</p>'),'Article');
const huge=retainPublicContactContext('Article',Array.from({length:100},(_,i)=>`<p>email${i}@example.org</p>`).join(''));
assert.ok(huge.length<6100);
console.log('contact context fixtures passed; no network used');
