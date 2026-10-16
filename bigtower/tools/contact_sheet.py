"""Generate labeled contact sheets from the Kenney TD pack to pick sprites."""
import os, sys
import pygame

SRC = os.path.join("assets", "packs", "kenney_tower-defense-top-down", "PNG", "Retina")
OUT = os.path.join("build", "contact")

def main():
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".png"))
    nums = [f for f in files]
    TILE = 96
    COLS = 8
    ROWS = 8
    PER = COLS * ROWS
    os.makedirs(OUT, exist_ok=True)
    font = pygame.font.Font(None, 22)
    for sheet_idx in range(0, len(nums), PER):
        batch = nums[sheet_idx:sheet_idx + PER]
        surf = pygame.Surface((COLS * TILE, ROWS * TILE))
        surf.fill((30, 30, 30))
        for i, name in enumerate(batch):
            img = pygame.image.load(os.path.join(SRC, name))  # no convert_alpha: broken under dummy driver
            img = pygame.transform.smoothscale(img, (TILE - 8, TILE - 8))
            col, row = i % COLS, i // COLS
            surf.blit(img, (col * TILE + 4, row * TILE + 14))
            label = font.render(name.replace("towerDefense_", "").replace(".png", ""), True, (255, 255, 0))
            surf.blit(label, (col * TILE + 4, row * TILE + 1))
        outp = os.path.join(OUT, f"sheet_{sheet_idx // PER}.png")
        pygame.image.save(surf, outp)
        print("wrote", outp, len(batch))
    pygame.quit()

if __name__ == "__main__":
    main()
