import 'package:carousel_slider/carousel_slider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_html/flutter_html.dart';
import 'package:google_fonts/google_fonts.dart';
import '../models/announcement.dart';

class AnnouncementCarousel extends StatelessWidget {
  final List<Announcement> announcements;

  const AnnouncementCarousel({super.key, required this.announcements});

  @override
  Widget build(BuildContext context) {
    if (announcements.isEmpty) {
      return const SizedBox.shrink();
    }

    return CarouselSlider(
      options: CarouselOptions(
        height: 200.0,
        autoPlay: true,
        enlargeCenterPage: true,
        viewportFraction: 0.85,
        aspectRatio: 16 / 9,
        autoPlayInterval: const Duration(seconds: 5),
        autoPlayAnimationDuration: const Duration(milliseconds: 800),
        autoPlayCurve: Curves.fastOutSlowIn,
      ),
      items: announcements.map((announcement) {
        return Builder(
          builder: (BuildContext context) {
            return Container(
              width: MediaQuery.of(context).size.width,
              margin: const EdgeInsets.symmetric(horizontal: 5.0),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(20),
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: _getGradientColors(announcement.type),
                ),
                boxShadow: [
                  BoxShadow(
                    color: _getShadowColor(
                      announcement.type,
                    ).withValues(alpha: 0.4),
                    blurRadius: 10,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Stack(
                  children: [
                    // Background Icon (Watermark)
                    Positioned(
                      right: -20,
                      top: -20,
                      child: Icon(
                        _getIcon(announcement.type),
                        size: 120,
                        color: Colors.white.withValues(alpha: 0.1),
                      ),
                    ),

                    // Content
                    Padding(
                      padding: const EdgeInsets.all(20.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Header: Type + Date
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.black.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  announcement.type.toUpperCase(),
                                  style: GoogleFonts.outfit(
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                    letterSpacing: 1.0,
                                  ),
                                ),
                              ),
                              Text(
                                announcement.date,
                                style: GoogleFonts.outfit(
                                  fontSize: 12,
                                  color: Colors.white.withValues(alpha: 0.9),
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),

                          // Title
                          Text(
                            announcement.title,
                            style: GoogleFonts.outfit(
                              fontSize: 18.0,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                              height: 1.2,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),

                          const Spacer(),

                          // HTML Content
                          // Using a fixed container to prevent overflow issues
                          SizedBox(
                            height: 60,
                            child: Html(
                              data: announcement.content,
                              style: {
                                "body": Style(
                                  color: Colors.white.withValues(alpha: 0.95),
                                  fontSize: FontSize(13.0),
                                  fontFamily: GoogleFonts.outfit().fontFamily,
                                  maxLines: 3,
                                  textOverflow: TextOverflow.ellipsis,
                                  margin: Margins.all(0),
                                  padding: HtmlPaddings.all(0),
                                ),
                                "p": Style(
                                  margin: Margins.all(0),
                                  padding: HtmlPaddings.all(0),
                                ),
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      }).toList(),
    );
  }

  List<Color> _getGradientColors(String type) {
    switch (type.toLowerCase()) {
      case 'urgente':
        return [
          const Color(0xFFEF4444),
          const Color(0xFFB91C1C),
        ]; // Red 500-700
      case 'importante':
        return [
          const Color(0xFFF59E0B),
          const Color(0xFFD97706),
        ]; // Amber 500-700
      case 'evento':
        return [
          const Color(0xFF10B981),
          const Color(0xFF059669),
        ]; // Emerald 500-700
      default: // info
        return [
          const Color(0xFF3B82F6),
          const Color(0xFF2563EB),
        ]; // Blue 500-700
    }
  }

  Color _getShadowColor(String type) {
    switch (type.toLowerCase()) {
      case 'urgente':
        return const Color(0xFFEF4444);
      case 'importante':
        return const Color(0xFFF59E0B);
      case 'evento':
        return const Color(0xFF10B981);
      default:
        return const Color(0xFF3B82F6);
    }
  }

  IconData _getIcon(String type) {
    switch (type.toLowerCase()) {
      case 'urgente':
        return Icons.warning_amber_rounded;
      case 'importante':
        return Icons.priority_high_rounded;
      case 'evento':
        return Icons.event;
      default:
        return Icons.info_outline;
    }
  }
}
