import pygame
from pathlib import Path

from .player import Player
from .platform import Platform
from .hazard import Hazard


# Colors
WHITE = (255, 255, 255)
BROWN = (150, 100, 60)
RED = (220, 60, 60)
GREEN = (0, 200, 0)
OVERLAY = (0, 0, 0, 190)

# Difficulty presets
DIFFICULTIES = {
    "Easy": {"gravity": 0.35, "jump_strength": 9},
    "Medium": {"gravity": 0.5, "jump_strength": 8},
    "Hard": {"gravity": 0.7, "jump_strength": 7},
}
DEFAULT_DIFFICULTY = "Medium"

# Sound effects
SOUND_NAMES = ("jump", "goal", "death")
SOUND_VOLUME = 0.5

# Keys
JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
MENU_UP_KEYS = (pygame.K_UP, pygame.K_w)
MENU_DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)
MENU_CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE)
QUIT_KEYS = (pygame.K_q, pygame.K_ESCAPE)


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        # Player
        self.start_x = 40
        self.start_y = height - 120
        self.player = Player(self.start_x, self.start_y)

        # Level: platforms with gaps between them (falling into a gap means
        # falling off the bottom of the screen), one hazard, and a goal
        # near the right edge.
        ground_y = height - 40
        self.platforms = [
            Platform(0, ground_y, 160),
            Platform(220, ground_y, 140),
            Platform(420, ground_y - 60, 120),
            Platform(600, ground_y, 180),
        ]
        self.hazards = [Hazard(240, ground_y - 14, 100)]
        self.goal_x = 740

        # Difficulty
        self.difficulties = DIFFICULTIES
        self.difficulty_names = list(self.difficulties.keys())
        self.selected_difficulty = self.difficulty_names.index(
            DEFAULT_DIFFICULTY
        )
        self.gravity = 0
        self.jump_strength = 0
        self.apply_difficulty()

        # Game state
        self.score = 0
        self.game_over = False
        self.game_over_reason = ""

        # Fonts
        self.font = pygame.font.SysFont("Arial", 30)
        self.game_over_font = pygame.font.SysFont("Arial", 56, bold=True)
        self.final_score_font = pygame.font.SysFont("Arial", 34)
        self.message_font = pygame.font.SysFont("Arial", 22)

        # Sound
        self.sounds = {}
        self.load_sounds()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def apply_difficulty(self):
        """Copy the selected difficulty's settings onto the engine."""
        name = self.difficulty_names[self.selected_difficulty]
        settings = self.difficulties[name]

        self.gravity = settings["gravity"]
        self.jump_strength = settings["jump_strength"]

    def load_sounds(self):
        """Load sound effects safely. The game still runs without audio."""
        self.sounds = {}

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error as error:
            print(f"Sound effects unavailable: {error}")
            return

        project_root = Path(__file__).resolve().parent.parent

        # Look in assets/ first, then assets/sounds/ as a fallback.
        search_dirs = [
            project_root / "assets",
            project_root / "assets" / "sounds",
        ]

        for name in SOUND_NAMES:
            sound_path = self.find_sound_file(search_dirs, name)

            if sound_path is None:
                print(f"Missing sound file: {name}.wav")
                continue

            try:
                sound = pygame.mixer.Sound(str(sound_path))
                sound.set_volume(SOUND_VOLUME)
                self.sounds[name] = sound
            except (pygame.error, OSError) as error:
                print(f"Could not load {sound_path.name}: {error}")

    @staticmethod
    def find_sound_file(search_dirs, name):
        """Return the path to <name>.wav in the first folder that has it."""
        for directory in search_dirs:
            candidate = directory / f"{name}.wav"

            if candidate.is_file():
                return candidate

        return None

    def play_sound(self, name):
        """Play a sound effect if it is available."""
        sound = self.sounds.get(name)

        if sound is None:
            return

        try:
            sound.play()
        except pygame.error:
            # Audio failure should not interrupt gameplay.
            pass

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.game_over:
            self.handle_game_over_event(event)
            return

        if event.key in JUMP_KEYS and self.player.on_ground:
            self.player.vy = -self.jump_strength
            self.player.on_ground = False
            self.play_sound("jump")

    def handle_game_over_event(self, event):
        """Game Over menu controls."""
        count = len(self.difficulty_names)

        if event.key in MENU_UP_KEYS:
            self.selected_difficulty = (self.selected_difficulty - 1) % count

        elif event.key in MENU_DOWN_KEYS:
            self.selected_difficulty = (self.selected_difficulty + 1) % count

        elif event.key in MENU_CONFIRM_KEYS:
            self.restart_game()

        elif event.key in QUIT_KEYS:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def handle_input(self):
        # Movement is frozen on the Game Over screen.
        if self.game_over:
            self.player.vx = 0
            return

        keys = pygame.key.get_pressed()
        self.player.vx = 0

        if any(keys[key] for key in LEFT_KEYS):
            self.player.vx -= self.player.speed

        if any(keys[key] for key in RIGHT_KEYS):
            self.player.vx += self.player.speed

    # ------------------------------------------------------------------
    # Game state
    # ------------------------------------------------------------------

    def reset_player(self):
        """Put the player back at the start with no movement."""
        self.player.x = self.start_x
        self.player.y = self.start_y
        self.player.vx = 0
        self.player.vy = 0
        self.player.on_ground = False

    def restart_game(self):
        """Start a fresh run using the selected difficulty."""
        self.apply_difficulty()
        self.reset_player()

        self.score = 0
        self.game_over = False
        self.game_over_reason = ""

    def end_game(self, reason):
        """Switch to the Game Over screen."""
        self.game_over = True
        self.game_over_reason = reason
        self.play_sound("death")

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self):
        # Do not update the game after Game Over.
        if self.game_over:
            return

        self.move_player()
        self.check_platform_landing()

        if self.check_hazards():
            return

        if self.check_fell_off_screen():
            return

        self.check_goal()

    def move_player(self):
        """Apply gravity and movement, remembering where the feet were."""
        self.previous_bottom = self.player.y + self.player.height

        self.player.vy += self.gravity

        new_x = self.player.x + self.player.vx
        max_x = self.width - self.player.width
        self.player.x = max(0, min(max_x, new_x))

        self.player.y += self.player.vy
        self.player.on_ground = False

    def check_platform_landing(self):
        """Land on the highest platform the player's feet crossed."""
        # Only land while falling (or standing still vertically).
        if self.player.vy < 0:
            return

        current_bottom = self.player.y + self.player.height
        player_left = self.player.x
        player_right = self.player.x + self.player.width

        landing_platform = None

        for platform in self.platforms:
            crossed_top = (
                self.previous_bottom <= platform.y
                and current_bottom >= platform.y
            )
            overlaps_horizontally = (
                player_right > platform.x
                and player_left < platform.x + platform.width
            )

            if not (crossed_top and overlaps_horizontally):
                continue

            if landing_platform is None or platform.y < landing_platform.y:
                landing_platform = platform

        if landing_platform is not None:
            self.player.y = landing_platform.y - self.player.height
            self.player.vy = 0
            self.player.on_ground = True

    def check_hazards(self):
        """End the game if the player touches a hazard."""
        player_rect = self.player.rect()

        for hazard in self.hazards:
            if player_rect.colliderect(hazard.rect()):
                self.end_game("You hit a hazard!")
                return True

        return False

    def check_fell_off_screen(self):
        """End the game if the player falls below the screen."""
        if self.player.y > self.height:
            self.end_game("You fell off the screen!")
            return True

        return False

    def check_goal(self):
        """Score a point and restart the level when the goal is reached."""
        if self.player.x < self.goal_x:
            return

        self.score += 1
        self.play_sound("goal")
        self.reset_player()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, screen):
        self.draw_world(screen)
        self.draw_hud(screen)

        if self.game_over:
            self.draw_game_over(screen)

    def draw_world(self, screen):
        for platform in self.platforms:
            pygame.draw.rect(screen, BROWN, platform.rect())

        for hazard in self.hazards:
            pygame.draw.rect(screen, RED, hazard.rect())

        goal_rect = pygame.Rect(self.goal_x, 0, 6, self.height)
        pygame.draw.rect(screen, GREEN, goal_rect)

        # Hide the player on the Game Over screen.
        if not self.game_over:
            pygame.draw.rect(screen, WHITE, self.player.rect())

    def draw_hud(self, screen):
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        screen.blit(score_text, (10, 10))

    def draw_centered(self, screen, font, text, color, y):
        """Render text horizontally centered at the given y position."""
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(self.width // 2, y))
        screen.blit(surface, rect)

    def draw_game_over(self, screen):
        center_y = self.height // 2

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(OVERLAY)
        screen.blit(overlay, (0, 0))

        self.draw_centered(
            screen, self.game_over_font, "GAME OVER", RED, center_y - 115
        )
        self.draw_centered(
            screen,
            self.final_score_font,
            f"Final Score: {self.score}",
            WHITE,
            center_y - 55,
        )
        self.draw_centered(
            screen,
            self.message_font,
            self.game_over_reason,
            WHITE,
            center_y - 15,
        )
        self.draw_centered(
            screen, self.message_font, "Choose Difficulty", WHITE, center_y + 25
        )

        for index, name in enumerate(self.difficulty_names):
            selected = index == self.selected_difficulty
            color = GREEN if selected else WHITE
            prefix = "> " if selected else "  "

            self.draw_centered(
                screen,
                self.message_font,
                f"{prefix}{name}",
                color,
                center_y + 60 + index * 30,
            )

        self.draw_centered(
            screen,
            self.message_font,
            "UP/DOWN: Select   ENTER: Replay   Q: Quit",
            WHITE,
            self.height - 35,
        )