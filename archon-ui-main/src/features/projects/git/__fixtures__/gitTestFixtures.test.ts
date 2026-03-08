/**
 * Tests for Git Test Fixtures
 *
 * These tests verify that frontend fixtures align with backend fixtures
 * for consistent testing across the stack.
 */

import { describe, expect, it } from "vitest";
import {
	fileStructureFixture,
	getFixture,
	getFixtureNames,
	gitTestFixtures,
	multiBranchFixture,
	simpleCommitsFixture,
} from "../__fixtures__";

describe("Git Test Fixtures", () => {
	describe("simpleCommitsFixture", () => {
		it("should have 3 commits", () => {
			expect(simpleCommitsFixture.commits).toHaveLength(3);
		});

		it("should have 1 branch (main)", () => {
			expect(simpleCommitsFixture.defaultBranch).toBe("main");
		});

		it("should have 3 files", () => {
			expect(simpleCommitsFixture.files).toHaveLength(3);
		});

		it("should have no binary files", () => {
			const binaryFiles = simpleCommitsFixture.files.filter((f) => f.is_binary);
			expect(binaryFiles).toHaveLength(0);
		});

		it("should have correct commit order (newest first)", () => {
			const commits = simpleCommitsFixture.commits;
			expect(commits[0].commit_sha).toBe("1eac0cd85a172f2e03709f41dc47f5c4356b3bde");
			expect(commits[1].commit_sha).toBe("9c61b1ad15472197d0f0e0126596aa722aad1735");
			expect(commits[2].commit_sha).toBe("9aebc994da52c9913be2898cb962e555b8397b0d");
		});

		it("should have expected file paths", () => {
			const filePaths = simpleCommitsFixture.files.map((f) => f.file_path);
			expect(filePaths).toContain("README.md");
			expect(filePaths).toContain("config.json");
			expect(filePaths).toContain("src/app.py");
		});
	});

	describe("multiBranchFixture", () => {
		it("should have 4 commits", () => {
			expect(multiBranchFixture.commits).toHaveLength(4);
		});

		it("should have merge commit with multiple parents", () => {
			const mergeCommit = multiBranchFixture.commits[0];
			expect(mergeCommit.parent_shas).toHaveLength(2);
		});

		it("should have files from all branches", () => {
			expect(multiBranchFixture.files).toHaveLength(3);
		});

		it("should identify merge commit correctly", () => {
			const mergeCommit = multiBranchFixture.commits[0];
			expect(mergeCommit.message).toContain("Merge");
		});
	});

	describe("fileStructureFixture", () => {
		it("should have 13 files", () => {
			expect(fileStructureFixture.files).toHaveLength(13);
		});

		it("should correctly identify PNG files as binary", () => {
			const pngFiles = fileStructureFixture.files.filter(
				(f) => f.file_extension === "png",
			);
			expect(pngFiles).toHaveLength(2);
			pngFiles.forEach((f) => {
				expect(f.is_binary).toBe(true);
			});
		});

		it("should correctly identify GIF as binary", () => {
			const gifFiles = fileStructureFixture.files.filter(
				(f) => f.file_extension === "gif",
			);
			expect(gifFiles).toHaveLength(1);
			expect(gifFiles[0].is_binary).toBe(true);
		});

		it("should correctly identify text files as non-binary", () => {
			const textFiles = fileStructureFixture.files.filter(
				(f) =>
					["ts", "tsx", "css", "md", "json"].includes(f.file_extension || "") &&
					!f.is_binary,
			);
			expect(textFiles.length).toBeGreaterThan(0);
		});

		it("should have source code files", () => {
			const sourceFiles = fileStructureFixture.files.filter((f) =>
				f.file_path.startsWith("src/"),
			);
			expect(sourceFiles).toHaveLength(5);
		});

		it("should have image files", () => {
			const imageFiles = fileStructureFixture.files.filter((f) =>
				f.file_path.startsWith("images/"),
			);
			expect(imageFiles).toHaveLength(3);
			expect(imageFiles.every((f) => f.is_binary)).toBe(true);
		});
	});

	describe("gitTestFixtures", () => {
		it("should export all fixtures", () => {
			expect(gitTestFixtures.simpleCommits).toBeDefined();
			expect(gitTestFixtures.multiBranch).toBeDefined();
			expect(gitTestFixtures.fileStructure).toBeDefined();
		});

		it("should have correct fixture names", () => {
			const names = getFixtureNames();
			expect(names).toContain("simpleCommits");
			expect(names).toContain("multiBranch");
			expect(names).toContain("fileStructure");
		});

		it("should retrieve fixture by name", () => {
			const fixture = getFixture("simpleCommits");
			expect(fixture.name).toBe("simple-commits");
		});
	});

	describe("Cross-fixture consistency", () => {
		it("all fixtures should have valid repository IDs", () => {
			Object.values(gitTestFixtures).forEach((fixture) => {
				expect(fixture.repository.id).toBeDefined();
				expect(fixture.repository.default_branch).toBeDefined();
			});
		});

		it("all fixtures should have commits with required fields", () => {
			Object.values(gitTestFixtures).forEach((fixture) => {
				fixture.commits.forEach((commit) => {
					expect(commit.commit_sha).toBeDefined();
					expect(commit.message).toBeDefined();
					expect(commit.author_name).toBeDefined();
					expect(commit.branches).toBeDefined();
				});
			});
		});

		it("all fixtures should have files with required fields", () => {
			Object.values(gitTestFixtures).forEach((fixture) => {
				fixture.files.forEach((file) => {
					expect(file.file_path).toBeDefined();
					expect(file.is_binary).toBeDefined();
				});
			});
		});

		it("all fixtures should have valid dates", () => {
			Object.values(gitTestFixtures).forEach((fixture) => {
				fixture.commits.forEach((commit) => {
					expect(commit.author_date).toMatch(/^\d{4}-\d{2}-\d{2}T/);
					expect(commit.commit_date).toMatch(/^\d{4}-\d{2}-\d{2}T/);
				});
			});
		});
	});
});
