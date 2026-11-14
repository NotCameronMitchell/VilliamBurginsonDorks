// Villiam Burginson Dorks: the game data (the .pck) comes in pieces, so every file stays
// small enough for any host (and for uploads from flaky connections). The pieces are
// fetched in parallel, written straight into one buffer and handed to the engine as its
// main pack. publish_web.ps1 fills in VBD_PARTS and has the page call this instead of
// Godot's own startGame.
const VBD_PARTS = __VBD_PARTS__; // [[file, size in bytes], ...] in order

function vbdStartGame(override) {
	const pack = GODOT_CONFIG['mainPack'] || (GODOT_CONFIG['executable'] + '.pck');
	const onProgress = (override && override['onProgress']) || function () {};
	const total = VBD_PARTS.reduce((sum, part) => sum + part[1], 0);
	const data = new Uint8Array(total);
	let loaded = 0;
	let offset = 0;
	const pieces = VBD_PARTS.map(([file, size]) => {
		const start = offset;
		offset += size;
		return fetch(file).then((response) => {
			if (!response.ok) {
				throw new Error('Could not load ' + file + ' (' + response.status + ')');
			}
			const reader = response.body.getReader();
			let at = start;
			function pump() {
				return reader.read().then(({ done, value }) => {
					if (done) {
						if (at !== start + size) {
							throw new Error(file + ' came out the wrong size. Please reload.');
						}
						return;
					}
					data.set(value, at);
					at += value.length;
					loaded += value.length;
					onProgress(loaded, total);
					return pump();
				});
			}
			return pump();
		});
	});
	return Promise.all([engine.init(GODOT_CONFIG['executable'])].concat(pieces))
		.then(() => engine.preloadFile(data.buffer, pack))
		.then(() => engine.start({ 'args': ['--main-pack', pack].concat(GODOT_CONFIG['args'] || []) }));
}
