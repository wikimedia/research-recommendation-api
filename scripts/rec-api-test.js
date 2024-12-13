#!/usr/bin/env node

/**
 * This script is intended to be a smoke test to be run against the recommendation API
 * after a deployment to ensure that the service is up and running as expected and
 * that all endpoints are minimally functional.
 *
 * Usage: `node rec-api-test.js [env]` where `env` is one of `production`, `staging`, or `wmcloud`
 */

const { describe, it } = require('node:test');
const assert = require('node:assert');

const ENVIROMENTS = ['production', 'staging', 'wmcloud']
let env = (process.argv[2] || 'production').toLowerCase()
if (!ENVIROMENTS.includes(env)) {
    console.warn(`Invalid environment: ${env}, defaulting to production`)
    env = 'production'
}

const getUrl = () => {
    switch (env) {
        case 'production':
            return 'https://api.wikimedia.org/service/lw/recommendation/api/v1/translation'
        case 'staging':
            return 'https://recommendation-api-ng.k8s-ml-staging.discovery.wmnet:31443/service/lw/recommendation/api/v1/translation'
        case 'wmcloud':
            return 'https://recommend.wmcloud.org/api/v1/translation'
    }
}

const query = async (params, path=null) => {
    let url = getUrl()
    if (path) {
        url += '/' + path
    }
    if (params) {
        url += '?' + new URLSearchParams(params)
    }
    return await (await fetch(url)).json()
}

const assertArrayNotEmpty = (array, name) => {
    assert(array, `${name} should be present`)
    assert(array.length > 0, `${name} should not be empty`)
}

const assertObjectNotEmpty = (object, name) => {
    assert(object, `${name} should be present`)
    assert(Object.keys(object).length > 0, `${name} should not be empty`)
}

const assertNumber = (value, name) => {
    assert(typeof value === 'number', `${name} should be a number`)
}

const assertPageRecommendations = (recommendations) => {
    assertArrayNotEmpty(recommendations, 'recommendations')
    assert.equal(recommendations.length, 10, 'count')
    const firstRecommendation = recommendations[0]
    assert(firstRecommendation.wikidata_id, 'wikidata_id')
    assertNumber(firstRecommendation.langlinks_count, 'langlinks_count')
    assertNumber(firstRecommendation.rank, 'rank')
}

const assertSectionsRecommendations = (recommendations) => {
    assertArrayNotEmpty(recommendations, 'recommendations')
    assert.equal(recommendations.length, 10, 'count')
    const firstRecommendation = recommendations[0]
    assert(firstRecommendation.source_title, 'source_title')
    assert(firstRecommendation.target_title, 'target_title')
    assertArrayNotEmpty(firstRecommendation.source_sections, 'source_sections')
    assertArrayNotEmpty(firstRecommendation.target_sections, 'target_sections')
    assert(firstRecommendation.present, 'present')
    assertObjectNotEmpty(firstRecommendation.missing, 'missing')
}

describe(`Recommendation API (${env})`, () => {
    it('Page collections', async () => {
        const pageCollections = await query(null, 'page-collections')
        assert(pageCollections.length > 0, 'pageCollections should not be empty')

        const firstCollection = pageCollections[0]
        assert(firstCollection.name, 'collection name')
        assertNumber(firstCollection.articles_count, 'collection articles_count')
    })

    describe('Article recommendations', () => {
        it('For you', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'sat',
                seed: 'Cat',
                search_algorithm: 'morelike',
                count: 10
            })
            assertPageRecommendations(recommendations)
        })

        it('Popular', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'sat',
                seed: 'Cat',
                search_algorithm: 'morelike',
                count: 10
            })
            assertPageRecommendations(recommendations)
        })

        it('Topics', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'sat',
                topics: 'history|visual-arts',
                count: 10
            })
            assertPageRecommendations(recommendations)
        })

        it('All collections', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'sat',
                count: 10,
                collections: true
            })
            assertPageRecommendations(recommendations)
        })
    })

    describe('Section recommendations', () => {
        it('For you', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'fr',
                seed: 'Cat',
                search_algorithm: 'morelike',
                count: 10
            }, 'sections')
            assertSectionsRecommendations(recommendations)
        })

        it('Popular', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'fr',
                seed: 'Cat',
                search_algorithm: 'morelike',
                count: 10
            }, 'sections')
            assertSectionsRecommendations(recommendations)
        })

        it('Topics', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'fr',
                topics: 'history|visual-arts',
                count: 10
            }, 'sections')
            assertSectionsRecommendations(recommendations)
        })

        it('All collections', async () => {
            const recommendations = await query({
                source: 'en',
                target: 'fr',
                count: 10,
                collections: true
            }, 'sections')
            assertSectionsRecommendations(recommendations)
        })
    })
})
 