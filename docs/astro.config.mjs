// @ts-check
// The shared max-models docs setup (@max-models/starlight-theme): served at
// https://max-models.github.io/scope-profiler-catalog/. A fork changes `repo` (and `owner`, `title`
// and `description`) here, and nothing else in this file.
import { defineDocs } from '@max-models/starlight-theme';

export default defineDocs({
	repo: 'scope-profiler-catalog',
	title: 'Profiling catalogue',
	description: 'A catalogue of profiling runs, built with scope-profiler and Astro.',
	// the front page is the catalogue's table of cases
	astro: { redirects: { '/': '/catalogue/' } },
	nav: [
		{ label: 'Catalogue', link: '/catalogue/' },
		{ label: 'Guide', link: '/guide/use-this-template/' },
	],
	sidebar: [
		{
			label: 'Catalogue',
			// written by `scope-profiler site` from catalogue.yaml
			items: [{ autogenerate: { directory: 'catalogue' } }],
		},
		{
			label: 'Guide',
			items: [
				{ label: 'Use this template', slug: 'guide/use-this-template' },
				{ label: 'The manifest', slug: 'guide/manifest' },
				{ label: 'Data and the workflow', slug: 'guide/workflow' },
			],
		},
	],
});
